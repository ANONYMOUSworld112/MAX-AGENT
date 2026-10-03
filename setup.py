#!/usr/bin/env python3
"""CyberBlack AI-agent MAX + MAX OS + LAYA — Automated Setup and Package Installer.

Dual-Mode Architecture:
1. Environment Setup Runner (default CLI):
   Creates runtime directories, installs requirements.txt, provisions Playwright
   browsers, and verifies OS compatibility. On Linux/macOS distros that block
   global pip installs (PEP 668), it automatically builds a local .venv and
   re-runs itself inside it.

   Usage:  python3 setup.py [--venv | --no-venv] [--with-deps] [--skip-browsers]

     --venv           force creating/using ./.venv
     --no-venv        install into the current interpreter (may fail under PEP 668)
     --with-deps      Linux: also install Playwright system libraries (asks for sudo)
     --skip-browsers  do not download Playwright browsers

2. Standard Setuptools Build/Install:
   Usage:  pip install -e .
"""

from __future__ import annotations

import ctypes.util
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

# Ensure UTF-8 output on Windows consoles / minimal Linux locales (C/POSIX)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.version_info < (3, 10):
    sys.exit(f"❌ Python 3.10+ is required (found {platform.python_version()}).")

OS = platform.system()  # "Windows" | "Darwin" | "Linux"
ROOT_DIR = Path(__file__).resolve().parent
VENV_DIR = ROOT_DIR / ".venv"
INSTALLER_FLAGS = {"--venv", "--no-venv", "--with-deps", "--skip-browsers"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def find_file(name: str) -> Path | None:
    """Case-insensitive file lookup in ROOT_DIR.

    Windows/macOS filesystems are case-insensitive, Linux is not: a repo that
    ships README.md would silently 'not have' readme.md on Linux.
    """
    wanted = name.lower()
    try:
        for child in ROOT_DIR.iterdir():
            if child.is_file() and child.name.lower() == wanted:
                return child
    except OSError:
        pass
    return None


def _run(label: str, args: list[str]) -> bool:
    """Run a command. Returns True on success, False on failure (never raises)."""
    print(f"\n▶ {label}")
    try:
        subprocess.run(args, check=True)
        return True
    except FileNotFoundError:
        print(f"❌ Command not found: {args[0]}")
    except subprocess.CalledProcessError as exc:
        print(f"❌ Command failed with exit code {exc.returncode}: {' '.join(map(str, args))}")
    return False


def in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def is_externally_managed() -> bool:
    """PEP 668: Debian 12+/Ubuntu 23.04+/Kali/Fedora/Homebrew refuse global pip installs."""
    try:
        return (Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED").exists()
    except Exception:
        return False


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if OS == "Windows" else "bin/python")


def bootstrap_venv(forward_flags: list[str]) -> None:
    """Create ./.venv (if needed) and re-run this script inside it."""
    py = venv_python()
    if not py.exists():
        print(f"\n▶ Creating virtual environment at {VENV_DIR} ...")
        try:
            import venv

            venv.EnvBuilder(with_pip=True).create(VENV_DIR)
        except Exception as exc:
            shutil.rmtree(VENV_DIR, ignore_errors=True)  # don't leave a half-built env
            print(f"❌ Could not create virtual environment: {exc}")
            if OS == "Linux":
                print("   Debian/Ubuntu/Kali fix:  sudo apt install python3-venv  (then re-run)")
            sys.exit(1)
    print(f"↪ Re-running setup inside {VENV_DIR}")
    sys.exit(subprocess.call([str(py), str(Path(__file__).resolve()), *forward_flags]))


def ensure_runtime_directories() -> None:
    """Creates essential runtime directories if missing."""
    for d in (ROOT_DIR / "config", ROOT_DIR / "memory", ROOT_DIR / "logs", ROOT_DIR / ".snapshots"):
        d.mkdir(parents=True, exist_ok=True)
    print("📁 Runtime directories verified (config, memory, logs, .snapshots).")


def check_linux_system_deps() -> None:
    """Best-effort check for native libs that pip cannot install (informational only)."""
    apt_pkgs: list[str] = []

    try:
        import tkinter  # noqa: F401  (pyautogui/mouseinfo import it)
    except ImportError:
        apt_pkgs.append("python3-tk")
    if not ctypes.util.find_library("portaudio"):  # sounddevice
        apt_pkgs.append("libportaudio2")
    if not (shutil.which("xclip") or shutil.which("xsel") or shutil.which("wl-copy")):  # pyperclip
        apt_pkgs.append("xclip")
    if not ctypes.util.find_library("xcb-cursor"):  # PyQt6 >= 6.5 xcb platform plugin
        apt_pkgs.append("libxcb-cursor0")

    if apt_pkgs:
        print("\n⚠️  Missing native libraries (pip cannot install these):")
        if shutil.which("apt-get"):
            print(f"    sudo apt install {' '.join(apt_pkgs)}")
        else:
            print(f"    Install the equivalents of: {', '.join(apt_pkgs)}")

    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print(
            "\n⚠️  No display server detected (headless / SSH). The PyQt6 UI and pyautogui\n"
            "    will crash on launch. Use a desktop session or run under: xvfb-run python main.py"
        )
    elif os.environ.get("XDG_SESSION_TYPE") == "wayland":
        print(
            "\nℹ️  Wayland session detected: pyautogui screenshots/mouse control are only reliable on X11.\n"
            "    For full desktop automation log in with an 'Xorg' session."
        )


def install_playwright(with_deps: bool) -> None:
    base = [sys.executable, "-m", "playwright", "install"]
    browsers = ["chromium", "firefox"]
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    want_deps = OS == "Linux" and (with_deps or is_root)

    ok = False
    if want_deps:
        ok = _run(
            "Installing Playwright browsers + system libraries (chromium + firefox)...",
            base + ["--with-deps"] + browsers,
        )
        if not ok:
            print("   --with-deps failed (unsupported distro?). Retrying browsers only...")
    if not ok:
        ok = _run("Installing Playwright browser engines (chromium + firefox)...", base + browsers)

    if not ok:
        print(f"⚠️  Playwright installation failed. Retry manually:\n    {sys.executable} -m playwright install chromium firefox")
    elif OS == "Linux" and not want_deps:
        print(
            "\nℹ️  If browsers fail to launch with 'missing dependencies', install system libs once with:\n"
            f"    sudo {sys.executable} -m playwright install-deps chromium firefox\n"
            "    (or re-run: python3 setup.py --with-deps)"
        )


# --------------------------------------------------------------------------- #
# Mode 1: environment installer
# --------------------------------------------------------------------------- #
def main_installer(flags: set[str]) -> None:
    """One-time environment setup for CyberBlack AI-agent MAX."""
    if "--venv" in flags and "--no-venv" in flags:
        sys.exit("❌ --venv and --no-venv cannot be combined.")

    needs_venv = "--venv" in flags or (is_externally_managed() and "--no-venv" not in flags)
    if needs_venv and not in_virtualenv():
        bootstrap_venv(sorted(flags))  # never returns

    print("=" * 70)
    print(f"⚙️  CyberBlack AI-agent MAX + MAX OS + LAYA: Setup — Detected OS: {OS or 'unknown'}")
    print(f"   Python Version: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 70)

    # 1. Directory structure
    ensure_runtime_directories()

    # 2. Python dependencies
    if in_virtualenv():
        _run("Upgrading pip...", [sys.executable, "-m", "pip", "install", "--upgrade", "pip"])  # non-fatal

    req_file = find_file("requirements.txt")
    if req_file:
        if not _run(
            "Installing Python dependencies (OS-specific platform markers auto-filtered)...",
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        ):
            print(
                "\n❌ Dependency installation failed. Common causes:\n"
                "   • Windows-only packages (pywin32, comtypes, ...) without a marker. Use e.g.:\n"
                '         pywin32>=306; sys_platform == "win32"\n'
                "   • 'externally-managed-environment' (PEP 668) -> run without --no-venv\n"
                "   • pip too old for modern wheels -> python3 -m pip install --upgrade pip"
            )
            sys.exit(1)
    else:
        print("⚠️  requirements.txt not found. Skipping pip install.")

    # 3. Playwright browser engines
    if "--skip-browsers" not in flags:
        install_playwright(with_deps="--with-deps" in flags)

    # 4. OS-specific configuration & verification
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
        check_linux_system_deps()
    elif OS == "Darwin":
        print(
            "\nℹ️  macOS note — volume, brightness, and reminders use native osascript/LaunchAgents.\n"
            "    For Safari browser automation: python -m playwright install webkit"
        )

    py = "python" if (OS == "Windows" or in_virtualenv()) else "python3"
    print("\n" + "=" * 70)
    print("✅ Setup complete!")
    step = 1
    if in_virtualenv() and Path(sys.prefix).resolve() == VENV_DIR.resolve():
        activate = r".venv\Scripts\activate" if OS == "Windows" else "source .venv/bin/activate"
        print(f"   {step}) Activate env:      {activate}")
        step += 1
    print(f"   {step}) Verify Test Suite: {py} -m pytest tests/ -v")
    print(f"   {step + 1}) Launch Assistant:  {py} main.py")
    print(f"   {step + 2}) Enter Gemini API key when prompted in the UI.")
    print(f"   {step + 3}) (Optional) Enable 'Hey MAX' wake word from ⚙ → WAKE WORD.")
    print("=" * 70 + "\n")


# --------------------------------------------------------------------------- #
# Mode 2: standard setuptools
# --------------------------------------------------------------------------- #
def _run_setuptools() -> None:
    """Standard setuptools packaging execution."""
    try:
        from setuptools import find_packages, setup
    except ImportError:
        print("❌ setuptools is required for build/install operations. Run: pip install setuptools")
        sys.exit(1)

    readme = find_file("readme.md")  # README.md / readme.md / Readme.md all work on Linux

    setup(
        name="cyberblack-ai-agent-max",
        version="3.0.0",
        description="CyberBlack AI-agent MAX: High-Reliability Autonomous Desktop Agent Swarm",
        long_description=readme.read_text(encoding="utf-8-sig") if readme else "",
        long_description_content_type="text/markdown",
        author="CyberBlack & MAX Autonomous Systems",
        packages=find_packages(include=["agents*", "core*", "actions*", "dashboard*", "ui*", "memory*"]),
        # Top-level main.py is not a package; without this the 'cyberblack-max'
        # console script fails with ModuleNotFoundError: No module named 'main'.
        py_modules=["main"] if (ROOT_DIR / "main.py").exists() else [],
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


if __name__ == "__main__":
    # Deterministic dispatch (replaces the old sys.modules sniffing):
    #   no args / only installer flags  -> environment installer
    #   anything else (egg_info, bdist_wheel, develop, --version, ...) -> setuptools
    cli_args = sys.argv[1:]
    if all(arg in INSTALLER_FLAGS for arg in cli_args):
        main_installer(set(cli_args))
    else:
        _run_setuptools()
