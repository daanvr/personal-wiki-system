"""Migration of legacy module configs (``modules/<m>/config`` in the system
repo) into the knowledge repo's settings home."""
from __future__ import annotations

import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from _shared.wikilib import read_kv, resolve_path

from . import manifest
from .secrets import SECRET_FILENAME

_SECRET_FILE_LINE = re.compile(r"(?m)^(#\s*)?SECRET_FILE\s*=.*$")


@dataclass
class Finding:
    module: manifest.Module
    old_config: Path
    old_secret: Path | None


def find_old(modules: list[manifest.Module]) -> list[Finding]:
    findings = []
    for module in modules:
        old_config = module.dir / "config"
        if not old_config.is_file():
            continue
        old_secret = None
        secret_ref = read_kv(old_config).get("SECRET_FILE")
        if secret_ref:
            candidate = Path(resolve_path(secret_ref, module.dir))
            if candidate.is_file():
                old_secret = candidate
        findings.append(Finding(module, old_config, old_secret))
    return findings


def run(io, findings: list[Finding], knowledge: Path, assume_yes: bool = False) -> None:
    for f in findings:
        new_dir = manifest.settings_dir(f.module, knowledge)
        new_config = new_dir / "config"
        if new_config.exists():
            io.warn(
                f"{f.module.title}: both {new_config} and the legacy "
                f"{f.old_config} exist. The legacy file is ignored — delete it "
                f"when convenient."
            )
            continue
        if not assume_yes and not io.confirm(
            f"Move {f.old_config} -> {new_config}?", default=True
        ):
            continue
        new_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f.old_config), str(new_config))
        if f.old_secret:
            new_secret = new_dir / SECRET_FILENAME
            shutil.move(str(f.old_secret), str(new_secret))
            try:
                new_secret.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
            text = new_config.read_text(encoding="utf-8")
            text = _SECRET_FILE_LINE.sub(f"SECRET_FILE={SECRET_FILENAME}", text, count=1)
            new_config.write_text(text, encoding="utf-8")
        io.info(f"  - migrated {f.module.title} config to {new_config}")
