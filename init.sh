#!/usr/bin/env bash
# Set up the wiki system — thin launcher for the Python setup wizard.
#
# Usage:
#   ./init.sh [path] [--list|--with NAME|--all-modules|--no-modules|--yes|...]
#
# All arguments are passed through to wizard.py (run `./init.sh --help` for
# the full list). The wizard scaffolds the knowledge base, offers each
# available module, and guides you through configuring and verifying it.
#
# Requires Python 3 (which every module needs anyway): `python3` on
# macOS/Linux, or the `py` launcher on Windows (Git Bash / WSL).
set -euo pipefail

SYSTEM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SYSTEM_ROOT/wizard.py" "$@"
elif command -v py >/dev/null 2>&1; then
  exec py -3 "$SYSTEM_ROOT/wizard.py" "$@"
else
  echo "error: Python 3 is required but was not found." >&2
  echo "Install it from https://www.python.org/downloads/ (or your package" >&2
  echo "manager), then re-run ./init.sh" >&2
  exit 1
fi
