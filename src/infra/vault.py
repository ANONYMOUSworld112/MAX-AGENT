"""
MAX OS — Vault Adapter (Secrets Management)
Build Order: #4 (Layer 1A)
═══════════════════════════════════════════════════════

Stores and retrieves sensitive keys (API tokens, PATs, passphrases).
Saves to encrypted file vault & OS keychain to guarantee key availability.
"""

from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

logger = logging.getLogger("max.infra.vault")

VAULT_DIR = Path.home() / ".max_os"
KEY_FILE = VAULT_DIR / "vault.key"
DATA_FILE = VAULT_DIR / "vault.enc"


class Vault:
    """Encrypted secrets vault."""

    def __init__(self):
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        self._fernet = self._get_or_create_fernet()

    def _get_or_create_fernet(self) -> Fernet:
        if KEY_FILE.exists():
            key = KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            KEY_FILE.write_bytes(key)
            os.chmod(KEY_FILE, 0o600)
        return Fernet(key)

    def set_secret(self, key_name: str, secret_value: str) -> None:
        """Store a secret securely in both encrypted file and OS keychain."""
        if not secret_value:
            return

        # 1. Store in encrypted file vault (guarantees local retrieval)
        secrets = self._read_encrypted_file()
        secrets[key_name] = secret_value
        self._write_encrypted_file(secrets)

        # 2. Store in OS keychain if available
        try:
            import keyring
            keyring.set_password("max_os", key_name, secret_value)
            logger.info("Stored secret '%s' in OS keychain", key_name)
        except Exception:
            pass

        logger.info("Stored secret '%s' in encrypted file vault", key_name)

    def get_secret(self, key_name: str) -> Optional[str]:
        """Retrieve a secret from env, encrypted file, or OS keychain."""
        # 1. Environment variable override
        env_val = os.environ.get(key_name) or os.environ.get(key_name.upper())
        if env_val:
            return env_val

        # 2. Encrypted file vault
        secrets = self._read_encrypted_file()
        if key_name in secrets and secrets[key_name]:
            return secrets[key_name]

        # 3. Keyring fallback
        try:
            import keyring
            val = keyring.get_password("max_os", key_name)
            if val:
                return val
        except Exception:
            pass

        return None

    def delete_secret(self, key_name: str) -> bool:
        """Delete a secret."""
        deleted = False
        secrets = self._read_encrypted_file()
        if key_name in secrets:
            del secrets[key_name]
            self._write_encrypted_file(secrets)
            deleted = True

        try:
            import keyring
            keyring.delete_password("max_os", key_name)
            deleted = True
        except Exception:
            pass

        return deleted

    def _read_encrypted_file(self) -> dict[str, str]:
        if not DATA_FILE.exists():
            return {}
        try:
            encrypted_data = DATA_FILE.read_bytes()
            decrypted = self._fernet.decrypt(encrypted_data).decode("utf-8")
            return json.loads(decrypted)
        except Exception as e:
            logger.error("Failed to read encrypted vault file: %s", e)
            return {}

    def _write_encrypted_file(self, secrets: dict[str, str]) -> None:
        raw_json = json.dumps(secrets).encode("utf-8")
        encrypted = self._fernet.encrypt(raw_json)
        DATA_FILE.write_bytes(encrypted)
        os.chmod(DATA_FILE, 0o600)


_global_vault: Optional[Vault] = None


def get_vault() -> Vault:
    global _global_vault
    if _global_vault is None:
        _global_vault = Vault()
    return _global_vault
