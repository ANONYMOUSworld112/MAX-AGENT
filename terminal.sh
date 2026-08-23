#!/usr/bin/env bash
# ==============================================================================
# MAX OS — Marvel AI Interactive Terminal Shell Launcher (terminal.sh)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 jarvis_terminal.py "$@"
