"""Tier 0 Characterization Test: App Normalization & Dashboard Security Helpers.

Tests open_app._normalize alias mapping and dashboard cryptographic key derivation.
"""
from actions.open_app import _normalize
from dashboard.server import _derive_key, _AES_SALT
import hashlib


def test_open_app_normalization():
    # Test canonical app aliases
    assert _normalize("chrome") in ("chrome", "Google Chrome", "google-chrome")
    assert _normalize("vscode") in ("code", "Visual Studio Code")
    assert _normalize("spotify") in ("Spotify", "spotify")
    # "calc" is a substring of "calculator", which normalizes to "calc.exe" on Windows
    assert _normalize("calc") in ("calc.exe", "Calculator", "gnome-calculator")
    assert _normalize("nonexistent_app_xyz") == "nonexistent_app_xyz"  # unmapped passes through


def test_dashboard_key_derivation():
    session_key = "TEST-SESSION-KEY-1234"
    derived = _derive_key(session_key)

    # SHA-256 is 32 bytes (256 bits)
    assert len(derived) == 32
    expected = hashlib.sha256(session_key.encode("utf-8") + _AES_SALT).digest()
    assert derived == expected
