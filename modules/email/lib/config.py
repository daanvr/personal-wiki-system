"""Configuration helpers for the email module.

A thin binding of the shared helpers in ``modules/_shared/wikilib.py`` to this
module's directory: account config, provider profiles, and the account secret.
"""
from __future__ import annotations

from pathlib import Path

from _shared import wikilib
from _shared.wikilib import (  # noqa: F401  (re-exported for module code)
    get_int,
    knowledge_path,
    read_kv,
    resolve_path,
    truthy,
)

# .../system/modules/email/lib/config.py -> parents[1] == .../modules/email
MODULE_DIR = Path(__file__).resolve().parents[1]


def load_account() -> dict[str, str]:
    """The module's account config (modules/email/config)."""
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
    wikilib.check_auth(prof)
    return prof


def get_secret(account: dict[str, str]) -> str:
    return wikilib.get_secret(account, MODULE_DIR)
