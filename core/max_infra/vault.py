"""Component #1: Vault Secrets Manager.

Secure credential storage integrating with OS Keyring (Windows Credential Manager / DPAPI)
with fallback to environment variables and in-memory cache.
Zero plain-text secrets in git commits or configuration logs.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Dict, Optional

logger = logging.getLogger("max.infra.vault")

try:
    import keyring  # type: ignore
    HAS_KEYRING = True
except ImportError:
    keyring = None  # type: ignore
    HAS_KEYRING = False


class Vault:
    _instance: Optional[Vault] = None
    _singleton_lock = threading.Lock()

    def __init__(self, use_keyring: bool = True) -> None:
        self.use_keyring = use_keyring and HAS_KEYRING
        self._memory_cache: Dict[str, str] = {}
        self._lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> Vault:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _canonical_key(self, service: str, key: str) -> str:
        return f"{service.lower().strip()}:{key.lower().strip()}"

    def _env_var_name(self, service: str, key: str) -> str:
        return f"MAX_VAULT_{service.upper().strip()}_{key.upper().strip()}"

    def store_secret(self, service_or_key: str, value_or_key: str, value: Optional[str] = None) -> None:
        if value is None:
            self.set_secret("default", service_or_key, value_or_key)
        else:
            self.set_secret(service_or_key, value_or_key, value)

    def set_secret(self, service: str, key: str, value: str) -> None:
        canonical = self._canonical_key(service, key)
        with self._lock:
            self._memory_cache[canonical] = value
            if self.use_keyring and keyring:
                try:
                    keyring.set_password(f"max_vault_{service}", key, value)
                except Exception as exc:
                    logger.warning("Keyring set_password failed, cached in memory: %s", exc)

    def get_secret(self, service_or_key: str, key: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
        if key is None:
            service = "default"
            actual_key = service_or_key
        else:
            service = service_or_key
            actual_key = key

        canonical = self._canonical_key(service, actual_key)
        with self._lock:
            # 1. Memory Cache
            if canonical in self._memory_cache:
                return self._memory_cache[canonical]

            # 2. Keyring
            if self.use_keyring and keyring:
                try:
                    val = keyring.get_password(f"max_vault_{service}", actual_key)
                    if val is not None:
                        self._memory_cache[canonical] = val
                        return val
                except Exception as exc:
                    logger.debug("Keyring get_password exception: %s", exc)

            # 3. Environment Variable Fallback
            env_key = self._env_var_name(service, actual_key)
            if env_key in os.environ:
                val = os.environ[env_key]
                self._memory_cache[canonical] = val
                return val

            return default

    def delete_secret(self, service: str, key: str) -> None:
        canonical = self._canonical_key(service, key)
        with self._lock:
            self._memory_cache.pop(canonical, None)
            if self.use_keyring and keyring:
                try:
                    keyring.delete_password(f"max_vault_{service}", key)
                except Exception:
                    pass
