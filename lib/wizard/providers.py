"""Provider profiles: listing, and creating a custom one.

Committed profiles live in the module's ``providers/``; user-created ones go
to the knowledge repo (``settings/modules/<m>/providers/``) so the system
repo stays pristine. A user profile with the same name overrides a committed
one. ``LABEL`` / ``APP_PASSWORD_HINT`` / ``DOCS_URL`` are presentation-only
keys the ingest engines ignore.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from _shared.wikilib import read_kv

from . import fields, manifest

_PRESENTATION_KEYS = {"LABEL", "APP_PASSWORD_HINT", "DOCS_URL"}
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass
class Profile:
    name: str
    label: str
    hint: str
    docs_url: str
    path: Path
    kv: dict


def _load(path: Path) -> Profile:
    kv = read_kv(path)
    return Profile(
        name=path.stem,
        label=kv.get("LABEL", path.stem),
        hint=kv.get("APP_PASSWORD_HINT", ""),
        docs_url=kv.get("DOCS_URL", ""),
        path=path,
        kv=kv,
    )


def user_providers_dir(module: manifest.Module, knowledge: Path) -> Path:
    return manifest.settings_dir(module, knowledge) / "providers"


def list_profiles(module: manifest.Module, knowledge: Path) -> list[Profile]:
    """Committed profiles merged with user ones (user wins by file name)."""
    merged: dict[str, Profile] = {}
    for base in (module.dir / "providers", user_providers_dir(module, knowledge)):
        if not base.is_dir():
            continue
        for conf in sorted(base.glob("*.conf")):
            if conf.stem.startswith("_"):
                continue
            merged[conf.stem] = _load(conf)
    return sorted(merged.values(), key=lambda p: p.name)


def create_custom(io, module: manifest.Module, knowledge: Path) -> Profile:
    """Prompt through the module's ``providers/_template.conf`` and write the
    result as a user profile in the knowledge repo."""
    template = module.dir / "providers" / "_template.conf"
    specs = fields.parse_example(template)

    def valid_name(name: str) -> str | None:
        if not _NAME_RE.match(name):
            return "Use lowercase letters, digits, dot, dash or underscore."
        return None

    name = io.ask("Short name for the new provider (e.g. fastmail)", validate=valid_name)
    answers: dict[str, str] = {"LABEL": io.ask("Display name", default=name.title())}
    for spec in specs:
        if spec.key in _PRESENTATION_KEYS and spec.key != "APP_PASSWORD_HINT":
            continue
        for line in spec.help_lines:
            io.info(f"  {line}")
        value = io.ask(spec.key, default=spec.default)
        if value or not spec.optional:
            answers[spec.key] = value

    out_dir = user_providers_dir(module, knowledge)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.conf"
    header = (
        f"# {answers['LABEL']} provider profile (user-created by the setup wizard).\n"
        f"# Connection details only — never put a password or personal data here.\n\n"
    )
    body = fields.render_config(template.read_text(encoding="utf-8"), answers)
    path.write_text(header + body, encoding="utf-8")
    io.info(f"Wrote provider profile {path}")
    return _load(path)
