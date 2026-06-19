"""Configuration helpers for the calendar module.

Reads the simple ``KEY=value`` files used across this repo, resolves the
knowledge base location, and looks up the account secret without storing it in
committed files.
"""
from __future__ import annotations

import os
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
SYSTEM_ROOT = Path(__file__).resolve().parents[3]


def read_kv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def resolve_path(p: str, base: Path) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (base / path)


def truthy(val) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def knowledge_path() -> Path:
    cfg = read_kv(SYSTEM_ROOT / "config")
    raw = cfg.get("KNOWLEDGE_PATH")
    if not raw:
        raise SystemExit(
            f"KNOWLEDGE_PATH not set in {SYSTEM_ROOT / 'config'} "
            f"(copy config.example to config, or run ./init.sh)."
        )
    return resolve_path(raw, SYSTEM_ROOT).resolve()


def load_account() -> dict[str, str]:
    cfg = read_kv(MODULE_DIR / "config")
    if not cfg:
        raise SystemExit(
            f"No account config at {MODULE_DIR / 'config'} "
            f"(copy config.example to config and fill it in)."
        )
    for required in ("PROVIDER", "ACCOUNT"):
        if not cfg.get(required):
            raise SystemExit(f"{required} is missing from {MODULE_DIR / 'config'}.")
    return cfg


def load_provider(name: str) -> dict[str, str]:
    path = MODULE_DIR / "providers" / f"{name}.conf"
    prof = read_kv(path)
    if not prof:
        raise SystemExit(f"Unknown or empty provider profile: {path}")
    if not prof.get("CALDAV_URL"):
        raise SystemExit(f"CALDAV_URL is missing from provider profile: {path}")
    return prof


def get_secret(account: dict[str, str]) -> str:
    ref = account.get("SECRET_REF")
    if ref and os.environ.get(ref):
        return os.environ[ref]

    secret_file = account.get("SECRET_FILE")
    if secret_file:
        path = resolve_path(secret_file, MODULE_DIR)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()

    hints = []
    if ref:
        hints.append(f"environment variable {ref} is unset")
    if secret_file:
        hints.append(f"file {secret_file} not found")
    if not hints:
        hints.append("set SECRET_REF (env var name) or SECRET_FILE in config")
    raise SystemExit("Could not resolve the account password: " + "; ".join(hints))
