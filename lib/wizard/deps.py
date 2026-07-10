"""Dependency checks: Python version and third-party imports."""
from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys

from . import manifest


def python_ok(module: manifest.Module) -> bool:
    if not module.requires_python:
        return True
    return sys.version_info[: len(module.requires_python)] >= module.requires_python


def missing_imports(module: manifest.Module) -> list[str]:
    missing = []
    for name in module.py_imports:
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(name)
    return missing


def ensure(io, module: manifest.Module) -> bool:
    """Check this module's requirements; offer to pip-install missing ones.
    Returns True when the module is runnable."""
    if not python_ok(module):
        wanted = ".".join(str(n) for n in module.requires_python)
        io.error(f"{module.title} needs Python >= {wanted} "
                 f"(this is {sys.version.split()[0]}).")
        return False

    missing = missing_imports(module)
    if not missing:
        return True

    io.warn(f"{module.title} needs Python packages that are not installed: "
            f"{', '.join(missing)}")
    if not module.has_requirements:
        io.info("Install them manually, then re-run the wizard.")
        return False

    req = module.dir / "requirements.txt"
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    if not io.confirm(f"Run `{' '.join(cmd)}` now?", default=True):
        io.info(f"Install later with: {' '.join(cmd)}")
        return False
    result = subprocess.run(cmd)
    if result.returncode != 0:
        io.error("pip install failed.")
        return False
    importlib.invalidate_caches()
    still_missing = missing_imports(module)
    if still_missing:
        io.error(f"Still missing after install: {', '.join(still_missing)}")
        return False
    return True
