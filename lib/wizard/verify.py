"""Live verification: run the module's own ``CHECK`` command.

The check runs as a subprocess with the module directory as cwd, exactly as a
user would run it. A session-only secret travels via the environment — never
on the command line.
"""
from __future__ import annotations

import os
import subprocess
import sys

from . import manifest


def run_check(module: manifest.Module, runtime_env: dict[str, str]) -> int:
    if not module.check_argv:
        return 0
    argv = [sys.executable] + module.check_argv
    env = os.environ.copy()
    env.update(runtime_env)
    result = subprocess.run(argv, cwd=module.dir, env=env)
    return result.returncode
