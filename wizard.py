#!/usr/bin/env python3
"""Setup wizard for the wiki system — the guided onboarding entry point.

Usually run via ``./init.sh`` (which finds a Python interpreter for you), but
running this file directly is equivalent:

    python3 wizard.py                 # interactive: scaffold + module setup
    python3 wizard.py /path/to/kb     # put the knowledge base somewhere specific
    python3 wizard.py --list          # show modules and their status
    python3 wizard.py --with email    # set up specific modules
    python3 wizard.py --all-modules   # set up every module
    python3 wizard.py --no-modules    # base scaffold only
    python3 wizard.py --yes           # non-interactive: defaults + scaffolded configs

Standard library only. See docs/setup-wizard.md for the module contract.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SYSTEM_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SYSTEM_ROOT / "modules"))  # _shared.wikilib
sys.path.insert(0, str(SYSTEM_ROOT / "lib"))      # the wizard package

from wizard import engine  # noqa: E402
from wizard.console import ConsoleIO  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Set up the knowledge base and optional ingestion modules.")
    parser.add_argument("knowledge_path", nargs="?",
                        help="where to create the knowledge base "
                             "(absolute, or relative to the system repo; default ../knowledge)")
    parser.add_argument("--list", action="store_true",
                        help="show available modules and their status, then exit")
    parser.add_argument("--with", dest="with_modules", action="append",
                        metavar="NAME", default=[],
                        help="set up a specific module (repeatable)")
    parser.add_argument("--all-modules", action="store_true",
                        help="set up every available module")
    parser.add_argument("--no-modules", action="store_true",
                        help="base scaffold only, skip module setup")
    parser.add_argument("--yes", action="store_true",
                        help="non-interactive: accept defaults and scaffold module "
                             "configs from their templates")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip the live connection checks")
    parser.add_argument("--migrate", action="store_true",
                        help="move legacy module configs into the knowledge repo "
                             "without asking")
    args = parser.parse_args(argv)

    io = ConsoleIO()
    try:
        return engine.run(io, args, SYSTEM_ROOT)
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130
    except EOFError:
        print("\nAborted (end of input).")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
