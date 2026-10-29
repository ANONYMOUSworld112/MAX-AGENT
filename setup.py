"""CyberBlack AI-agent MAX + MAX OS + LAYA — Automated Setup and Package Installer.

Dual-Mode Architecture:
1. Environment Setup Runner (Default CLI):
   Executes one-time setup: installs dependencies from requirements.txt,
   provisions Playwright browser engines, ensures necessary runtime directories,
   and verifies operating system compatibility.
   Usage: python setup.py

2. Standard Setuptools Build/Install:
   Supports standard Python packaging commands (pip install -e ., python setup.py install, etc.).
   Usage: pip install -e .
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles to prevent charmap encoding errors
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OS = platform.system()  # "Windows" | "Darwin" | "Linux"
ROOT_DIR = Path(__file__).resolve().parent


def _run(label: str, args: list[str]) -> None:
    print(f"\n▶ {label}")
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"❌ Command failed with exit code {exc.returncode}: {' '.join(args)}")
        raise


def ensure_runtime_directories() -> None:
    """Creates essential runtime directories and template files if missing."""
    import shutil

    dirs = [
        ROOT_DIR / "config",
        ROOT_DIR / "memory",
        ROOT_DIR / "memory" / "backups",
        ROOT_DIR / "logs",
        ROOT_DIR / "notes",
        ROOT_DIR / ".snapshots",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Initialize .gitkeep files for clean state
    for keep_dir in (ROOT_DIR / "logs", ROOT_DIR / "notes", ROOT_DIR / "memory" / "backups"):
        keep_file = keep_dir / ".gitkeep"
        if not keep_file.exists():
            keep_file.write_text("", encoding="utf-8")

    # Initialize configuration templates if not present
    api_keys_file = ROOT_DIR / "config" / "api_keys.json"
    api_keys_example = ROOT_DIR / "config" / "api_keys.example.json"
    if not api_keys_file.exists() and api_keys_example.exists():
        shutil.copyfile(api_keys_example, api_keys_file)
        print("📋 Initialized config/api_keys.json from clean template.")

    env_file = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copyfile(env_example, env_file)
        print("📋 Initialized .env from clean template.")

    print("📁 Runtime directories verified (config, memory, logs, notes, .snapshots).")


def main_installer() -> None:
    """One-time environment setup for CyberBlack AI-agent MAX."""
    print("=" * 70)
    print(f"⚙️  CyberBlack AI-agent MAX + MAX OS + LAYA: Setup — Detected OS: {OS or 'unknown'}")
    print(f"   Python Version: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 70)

    # 1. Directory Structure & Templates
    ensure_runtime_directories()

    # 2. Python Dependencies
    req_file = ROOT_DIR / "requirements.txt"
    if req_file.exists():
        _run(
            "Installing Python dependencies (OS-specific platform markers auto-filtered)...",
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        )
    else:
        print("⚠️  requirements.txt not found. Skipping pip install.")

    # 3. Playwright Browser Engines
    try:
        _run(
            "Installing Playwright browser engines (chromium + firefox)...",
            [sys.executable, "-m", "playwright", "install", "chromium", "firefox"],
        )
    except Exception as exc:
        print(f"⚠️  Playwright browser installation warning: {exc}")
        print("   You can retry manually via: python -m playwright install chromium firefox")

    # 4. OS-Specific Configuration & Verification
    if OS == "Windows":
        try:
            import win32com.client  # noqa: F401
            print("✅ pywin32 COM client successfully registered.")
        except ImportError:
            postinstall = Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py"
            print(
                "\n⚠️  pywin32 did not register correctly. If desktop automation fails, run:\n"
                f'    "{sys.executable}" -m pip install --force-reinstall pywin32\n'
                f'    "{sys.executable}" "{postinstall}" -install'
            )
    elif OS == "Linux":
        print(
            "\nℹ️  Linux note — OS actions shell out to native tools:\n"
            "    • volume      → pulseaudio-utils (pactl)\n"
            "    • brightness  → brightnessctl\n"
            "    • reminders   → systemd (systemd-run) or 'at'\n"
            "    • open URLs   → xdg-utils (xdg-open)"
        )
    elif OS == "Darwin":
        print(
            "\nℹ️  macOS note — volume, brightness, and reminders use native osascript/LaunchAgents.\n"
            "    For Safari browser automation: python -m playwright install webkit"
        )

    print("\n" + "=" * 70)
    print("✅ Setup complete! Quick Start Options:")
    print("   1) Run Voice HUD (PyQt6 Dark Interface): python main.py")
    print("   2) Run CLI Chat (Fast Terminal Agent):   python friday_cli.py")
    print("   3) Verify Test Suite (100% Passing):     python -m pytest")
    print("   4) Provide API Key in .env or enter it when prompted on launch.")
    print("=" * 70 + "\n")


def _run_setuptools() -> None:
    """Standard setuptools packaging execution."""
    try:
        from setuptools import find_packages, setup
    except ImportError:
        print("❌ setuptools is required for build/install operations. Run: pip install setuptools")
        sys.exit(1)

    setup(
        name="cyberblack-ai-agent-max",
        version="3.1.0",
        description="CyberBlack AI-agent MAX: High-Reliability Autonomous Desktop Agent Swarm & Voice AI",
        long_description=(
            (ROOT_DIR / "README.md").read_text(encoding="utf-8")
            if (ROOT_DIR / "README.md").exists()
            else (ROOT_DIR / "readme.md").read_text(encoding="utf-8")
            if (ROOT_DIR / "readme.md").exists()
            else ""
        ),
        long_description_content_type="text/markdown",
        author="CyberBlack & MAX Autonomous Systems",
        packages=find_packages(
            include=[
                "agents*",
                "core*",
                "actions*",
                "dashboard*",
                "ui*",
                "memory*",
                "workers*",
                "tools*",
                "skills*",
            ]
        ),
        python_requires=">=3.11",
        entry_points={
            "console_scripts": [
                "cyberblack-max=main:main",
                "friday=friday_cli:main",
                "max-cli=friday_cli:main",
            ],
        },
        install_requires=[
            "PyQt6>=6.5.0",
            "sounddevice>=0.4.6",
            "numpy>=1.24.0",
            "google-genai>=2.8.0",
            "requests>=2.31.0",
            "beautifulsoup4>=4.12.0",
            "ddgs>=7.0.0",
            "playwright>=1.40.0",
            "pyautogui>=0.9.54",
            "pyperclip>=1.8.2",
            "pygetwindow>=0.0.9",
            "psutil>=5.9.0",
            "fastapi>=0.110.0",
            "uvicorn>=0.27.0",
            "cryptography>=42.0.0",
            "pillow>=10.0.0",
            "opencv-python>=4.8.0",
            "mss>=9.0.0",
            "send2trash>=1.8.0",
            "pydantic>=2.0.0",
            "pydantic-settings>=2.0.0",
            "pyyaml>=6.0",
            "qrcode[pil]>=7.4.2",
            "httpx>=0.27.0",
        ],
        extras_require={
            "test": [
                "pytest>=7.4.0",
                "pytest-asyncio>=0.21.0",
                "pytest-cov>=4.1.0",
                "hypothesis>=6.90.0",
            ],
            "wake_word": [
                "openwakeword>=0.6.0",
            ],
        },
    )


def is_build_tool() -> bool:
    """Returns True if executed inside pip/setuptools/build isolation."""
    build_indicators = ("setuptools.build_meta", "pip", "build", "wheel")
    return any(ind in sys.modules for ind in build_indicators)


if __name__ == "__main__":
    standard_cmds = {
        "install", "develop", "bdist_wheel", "sdist", "egg_info",
        "build", "dist_info", "clean", "editable_wheel", "--help", "-h",
    }
    has_setuptools_arg = len(sys.argv) > 1 and any(arg in standard_cmds for arg in sys.argv[1:])

    if is_build_tool() or has_setuptools_arg:
        _run_setuptools()
    else:
        main_installer()

