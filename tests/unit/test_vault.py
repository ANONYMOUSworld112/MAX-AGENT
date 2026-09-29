import pytest
from core.max_infra.vault import Vault

def test_vault_in_memory_and_env():
    vault = Vault(use_keyring=False)
    assert vault.get_secret("test_service", "api_key") is None

    vault.set_secret("test_service", "api_key", "secret_value_123")
    assert vault.get_secret("test_service", "api_key") == "secret_value_123"

    vault.delete_secret("test_service", "api_key")
    assert vault.get_secret("test_service", "api_key") is None

def test_vault_env_fallback(monkeypatch):
    monkeypatch.setenv("MAX_VAULT_GEMINI_API_KEY", "env_key_xyz")
    vault = Vault(use_keyring=False)
    assert vault.get_secret("gemini", "api_key") == "env_key_xyz"
