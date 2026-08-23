"""
MAX OS — Local Encrypted Vault

Credential interface backed by OS keychain (`keyring` library) with an encrypted
file fallback (`cryptography` Fernet/AES) for headless/CI environments.

Design:
  - Agents request secrets at runtime via get_secret(service, key).
  - Secrets are NEVER saved in plaintext files, .env files, or code.
  - See DECISIONS.md D6, ARCHITECTURE.md step 0.3.

Acceptance criteria:
  - No plaintext key/token anywhere in the repo, including test fixtures.
  - Tests confirm retrieving a stored key via the Vault interface works and
    reading underlying file/storage directly does not expose it in plaintext.
"""

import base64
import os
import logging
from pathlib import Path
from typing import Optional

try:
    import keyring
    from keyring.errors import KeyringError
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    class KeyringError(Exception): pass
    KEYRING_AVAILABLE = False
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("max.vault")

SYSTEM_NAME = "MAX_OS_Vault"
FALLBACK_VAULT_DIR = Path.home() / ".max_os"
FALLBACK_VAULT_FILE = FALLBACK_VAULT_DIR / "vault.enc"
FALLBACK_SALT_FILE = FALLBACK_VAULT_DIR / "vault.salt"


class VaultError(Exception):
    """Base exception for Vault errors."""
    pass


class Vault:
    """
    Secure Vault interface for managing application secrets and credentials.
    Uses OS Keyring primary backend, falling back to AES-Fernet encrypted storage
    when OS keyring is unavailable (e.g. headless servers / CI).
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or FALLBACK_VAULT_DIR
        self.vault_file = self.storage_dir / "vault.enc"
        self.salt_file = self.storage_dir / "vault.salt"
        self._fernet: Optional[Fernet] = None

    def _get_fernet(self) -> Fernet:
        """Initialize or get Fernet cipher using machine-derived key."""
        return self._init_fernet()

    def _init_fernet(self) -> Fernet:
        """Derive an encryption key from machine-specific identifiers + persistent salt."""
        if self._fernet is not None:
            return self._fernet

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        if self.salt_file.exists():
            salt = self.salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            self.salt_file.write_bytes(salt)
            # Restrict permissions where supported
            try:
                os.chmod(self.salt_file, 0o600)
            except Exception:
                pass

        # Derive key using machine seed
        machine_seed = f"{os.getlogin() if hasattr(os, 'getlogin') else 'max_user'}-{os.name}".encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_seed))
        self._fernet = Fernet(key)
        return self._fernet

    def _full_key(self, service: str, key_name: str) -> str:
        return f"{service}:{key_name}"

    def store_secret(self, service: str, key_name: str, secret_value: str) -> None:
        """
        Store a secret in the vault.
        Attempts OS keyring first, falls back to encrypted storage file.
        """
        if not service or not key_name or secret_value is None:
            raise VaultError("Service, key_name, and secret_value must be provided")

        full_key = self._full_key(service, key_name)
        keyring_success = False

        if KEYRING_AVAILABLE and keyring:
            try:
                keyring.set_password(SYSTEM_NAME, full_key, secret_value)
                keyring_success = True
                logger.debug("Successfully saved secret to OS keyring")
            except (KeyringError, Exception) as e:
                logger.warning(f"OS keyring unavailable for store ({e}), using encrypted fallback")

        # Always also sync to encrypted fallback storage if keyring fails or for backup
        if not keyring_success:
            self._store_encrypted_fallback(full_key, secret_value)

    def get_secret(self, service: str, key_name: str) -> Optional[str]:
        """
        Retrieve a secret from the vault.
        Checks OS keyring first, then encrypted fallback storage.
        """
        full_key = self._full_key(service, key_name)

        if KEYRING_AVAILABLE and keyring:
            try:
                val = keyring.get_password(SYSTEM_NAME, full_key)
                if val is not None:
                    return val
            except (KeyringError, Exception) as e:
                logger.warning(f"OS keyring unavailable for read ({e}), trying encrypted fallback")

        return self._get_encrypted_fallback(full_key)

    def delete_secret(self, service: str, key_name: str) -> bool:
        """
        Delete a secret from the vault.
        Returns True if deleted from either keyring or fallback storage.
        """
        full_key = self._full_key(service, key_name)
        deleted = False

        if KEYRING_AVAILABLE and keyring:
            try:
                keyring.delete_password(SYSTEM_NAME, full_key)
                deleted = True
            except (KeyringError, Exception):
                pass

        if self._delete_encrypted_fallback(full_key):
            deleted = True

        return deleted

    # --- Encrypted Fallback Helpers ---

    def _read_fallback_data(self) -> dict:
        if not self.vault_file.exists():
            return {}
        try:
            cipher = self._init_fernet()
            encrypted_data = self.vault_file.read_bytes()
            if not encrypted_data:
                return {}
            decrypted_raw = cipher.decrypt(encrypted_data).decode("utf-8")
            import json
            return json.loads(decrypted_raw)
        except Exception as e:
            logger.error(f"Error reading encrypted fallback vault: {e}")
            return {}

    def _write_fallback_data(self, data: dict) -> None:
        cipher = self._init_fernet()
        import json
        raw_bytes = json.dumps(data).encode("utf-8")
        encrypted = cipher.encrypt(raw_bytes)
        self.vault_file.write_bytes(encrypted)
        try:
            os.chmod(self.vault_file, 0o600)
        except Exception:
            pass

    def _store_encrypted_fallback(self, full_key: str, value: str) -> None:
        data = self._read_fallback_data()
        data[full_key] = value
        self._write_fallback_data(data)

    def _get_encrypted_fallback(self, full_key: str) -> Optional[str]:
        data = self._read_fallback_data()
        return data.get(full_key)

    def _delete_encrypted_fallback(self, full_key: str) -> bool:
        data = self._read_fallback_data()
        if full_key in data:
            del data[full_key]
            self._write_fallback_data(data)
            return True
        return False


# Global default instance
_vault_instance: Optional[Vault] = None


def get_vault() -> Vault:
    """Get global Vault instance."""
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = Vault()
    return _vault_instance
