"""Configuration helpers for the calendar module.

A thin binding of the shared helpers in ``modules/_shared/wikilib.py`` to this
module's directory: account config, provider profiles, and the account secret.
The account config lives in the knowledge repo's settings home
(``<knowledge>/settings/modules/calendar/config``); the legacy module-local
``config`` still works as a fallback.
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

# .../system/modules/calendar/lib/config.py -> parents[1] == .../modules/calendar
MODULE_DIR = Path(__file__).resolve().parents[1]

# Directory of the resolved account config; SECRET_FILE resolves against it.
_config_dir: Path | None = None


def load_account() -> dict[str, str]:
    """The module's account config (knowledge settings home, or legacy
    modules/calendar/config)."""
    global _config_dir
    cfg, path = wikilib.load_module_account(MODULE_DIR)
    _config_dir = path.parent
    return cfg


def load_provider(name: str) -> dict[str, str]:
    path = wikilib.find_provider_profile(MODULE_DIR, name)
    prof = read_kv(path) if path else {}
    if not prof:
        raise SystemExit(
            f"Unknown or empty provider profile: {name!r} "
            f"(looked in {wikilib.module_settings_dir(MODULE_DIR.name) / 'providers'} "
            f"and {MODULE_DIR / 'providers'})."
        )
    if not prof.get("CALDAV_URL"):
        raise SystemExit(f"CALDAV_URL is missing from provider profile: {path}")
    wikilib.check_auth(prof)
    return prof


def get_secret(account: dict[str, str]) -> str:
    return wikilib.get_secret(account, _config_dir or MODULE_DIR)
