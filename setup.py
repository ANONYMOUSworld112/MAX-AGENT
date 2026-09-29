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
    """Creates essential runtime directories if missing."""
    dirs = [
        ROOT_DIR / "config",
        ROOT_DIR / "memory",
        ROOT_DIR / "logs",
        ROOT_DIR / ".snapshots",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("📁 Runtime directories verified (config, memory, logs, .snapshots).")


def main_installer() -> None:
    """One-time environment setup for CyberBlack AI-agent MAX."""
    print("=" * 70)
    print(f"⚙️  CyberBlack AI-agent MAX + MAX OS + LAYA: Setup — Detected OS: {OS or 'unknown'}")
    print(f"   Python Version: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 70)

    # 1. Directory Structure
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
    print("✅ Setup complete!")
    print("   1) Verify Test Suite:  python -m pytest tests/ -v")
    print("   2) Launch Assistant:   python main.py")
    print("   3) Enter Gemini API key when prompted in the UI.")
    print("   4) (Optional) Enable 'Hey MAX' wake word from ⚙ → WAKE WORD.")
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
        version="3.0.0",
        description="CyberBlack AI-agent MAX: High-Reliability Autonomous Desktop Agent Swarm",
        long_description=(ROOT_DIR / "readme.md").read_text(encoding="utf-8") if (ROOT_DIR / "readme.md").exists() else "",
        long_description_content_type="text/markdown",
        author="CyberBlack & MAX Autonomous Systems",
        packages=find_packages(include=["agents*", "core*", "actions*", "dashboard*", "ui*", "memory*"]),
        python_requires=">=3.10",
        entry_points={
            "console_scripts": [
                "cyberblack-max=main:main",
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
            "psutil>=5.9.0",
            "fastapi>=0.110.0",
            "uvicorn>=0.27.0",
            "cryptography>=42.0.0",
        ],
        extras_require={
            "test": [
                "pytest>=7.4.0",
                "pytest-asyncio>=0.21.0",
                "pytest-cov>=4.1.0",
                "hypothesis>=6.90.0",
                "httpx>=0.27.0",
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

