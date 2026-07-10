"""Module discovery: the ``module.conf`` contract.

A module is any ``modules/<name>/`` folder with a ``module.conf`` manifest
(KEY=value, parsed never executed). "Enabled" means the module has a config
in the knowledge repo's settings home — state is derived from the filesystem,
there is no registry.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

from _shared.wikilib import read_kv


@dataclass
class Module:
    name: str
    dir: Path
    title: str
    description: str
    check_argv: list[str] = field(default_factory=list)
    requires_python: tuple[int, ...] | None = None
    py_imports: list[str] = field(default_factory=list)
    has_requirements: bool = False


def _parse_version(raw: str) -> tuple[int, ...] | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return None


def discover(system_root: Path) -> list[Module]:
    """Every module under ``modules/`` that ships a ``module.conf``."""
    modules = []
    for conf in sorted((system_root / "modules").glob("*/module.conf")):
        mdir = conf.parent
        if mdir.name.startswith("_"):
            continue
        kv = read_kv(conf)
        modules.append(Module(
            name=mdir.name,
            dir=mdir,
            title=kv.get("TITLE", mdir.name),
            description=kv.get("DESCRIPTION", ""),
            check_argv=shlex.split(kv.get("CHECK", "")),
            requires_python=_parse_version(kv.get("REQUIRES_PYTHON", "")),
            py_imports=[m.strip() for m in kv.get("PY_IMPORTS", "").split(",") if m.strip()],
            has_requirements=(mdir / "requirements.txt").is_file(),
        ))
    return modules


def settings_dir(module: Module, knowledge: Path) -> Path:
    return knowledge / "settings" / "modules" / module.name


def config_path(module: Module, knowledge: Path) -> Path:
    return settings_dir(module, knowledge) / "config"


def is_enabled(module: Module, knowledge: Path) -> bool:
    return config_path(module, knowledge).is_file()
