"""Helpers shared by all ingestion modules.

Single source of truth for the ``KEY=value`` config format, knowledge-base
resolution (the same contract as the repo's ``lib/config.sh``), secret lookup,
filesystem-safe naming, YAML escaping, note-template rendering, and sync-state
persistence. Each module keeps a thin ``lib/config.py`` that binds these
helpers to its own directory.

Standard library only, so the email module stays dependency-free.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path

# .../system/modules/_shared/wikilib.py -> parents[2] == .../system
SYSTEM_ROOT = Path(__file__).resolve().parents[2]


# --- config files ------------------------------------------------------------

def read_kv(path: Path) -> dict[str, str]:
    """Parse a ``KEY=value`` file. Blank lines and ``#`` comments are
    ignored. Returns ``{}`` if the file does not exist."""
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
    """Absolute paths pass through; relative paths resolve against ``base``."""
    path = Path(p)
    return path if path.is_absolute() else (base / path)


def truthy(val) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def get_int(mapping: dict[str, str], key: str, default: int) -> int:
    """An integer config value, with a friendly error instead of a traceback."""
    raw = str(mapping.get(key, default)).strip()
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"Expected a number for {key}, got {raw!r}.") from None


def knowledge_path() -> Path:
    """Absolute path to the knowledge base, from the repo-root ``config``."""
    cfg = read_kv(SYSTEM_ROOT / "config")
    raw = cfg.get("KNOWLEDGE_PATH")
    if not raw:
        raise SystemExit(
            f"KNOWLEDGE_PATH not set in {SYSTEM_ROOT / 'config'} "
            f"(copy config.example to config, or run ./init.sh)."
        )
    return resolve_path(raw, SYSTEM_ROOT).resolve()


def settings_dir() -> Path:
    """User configuration home inside the (private) knowledge repo."""
    return knowledge_path() / "settings"


def module_settings_dir(name: str) -> Path:
    """A module's configuration directory in the knowledge repo."""
    return settings_dir() / "modules" / name


def find_module_config(module_dir: Path) -> Path | None:
    """Resolve a module's account config: the knowledge-repo settings home
    first, then the legacy module-local location (with a warning)."""
    new = module_settings_dir(module_dir.name) / "config"
    if new.is_file():
        return new
    old = module_dir / "config"
    if old.is_file():
        print(
            f"warning: reading legacy config at {old}; "
            f"run ./init.sh to migrate it to {new}",
            file=sys.stderr,
        )
        return old
    return None


def load_module_account(
    module_dir: Path, required: tuple[str, ...] = ("PROVIDER", "ACCOUNT")
) -> tuple[dict[str, str], Path]:
    """A module's account config plus the path it was resolved from."""
    path = find_module_config(module_dir)
    cfg = read_kv(path) if path else {}
    if not cfg:
        raise SystemExit(
            f"No account config for module {module_dir.name!r} "
            f"(expected {module_settings_dir(module_dir.name) / 'config'}; "
            f"run ./init.sh to set it up)."
        )
    for key in required:
        if not cfg.get(key):
            raise SystemExit(f"{key} is missing from {path}.")
    return cfg, path


def find_provider_profile(module_dir: Path, name: str) -> Path | None:
    """Resolve a provider profile: user profiles in the knowledge repo first
    (they may override a committed one), then the module's providers/."""
    for base in (
        module_settings_dir(module_dir.name) / "providers",
        module_dir / "providers",
    ):
        path = base / f"{name}.conf"
        if path.is_file():
            return path
    return None


def check_auth(provider: dict[str, str]) -> None:
    """Fail fast on an AUTH method the code does not actually implement."""
    method = provider.get("AUTH", "password").strip().lower()
    if method != "password":
        raise SystemExit(
            f"Unsupported auth method: {method!r} (only 'password' is supported)."
        )


def get_secret(account: dict[str, str], module_dir: Path) -> str:
    """Resolve the password from the env var named in SECRET_REF, falling
    back to the file named in SECRET_FILE. Never read from a committed file."""
    ref = account.get("SECRET_REF")
    if ref and os.environ.get(ref):
        return os.environ[ref]

    secret_file = account.get("SECRET_FILE")
    if secret_file:
        path = resolve_path(secret_file, module_dir)
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


# --- naming / paths ----------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WIN_DEVICES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_name(name: str) -> str:
    """A name safe to use as a file or directory on every platform: strips
    reserved characters and defuses Windows device names (CON, NUL, ...)."""
    name = _UNSAFE_CHARS.sub("_", name).strip().strip(".")
    if name.split(".")[0].upper() in _WIN_DEVICES:
        name = "_" + name
    return name or "unnamed"


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:60].strip("-")


# --- rendering ---------------------------------------------------------------

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_TOKEN = re.compile(r"\{\{(\w+)\}\}")


def yaml_escape(s: str) -> str:
    """Safe inside a double-quoted YAML scalar: escapes backslash and quote,
    and flattens newlines and other control characters to spaces."""
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    return _CONTROL_CHARS.sub(" ", s)


def render_template(template: str, fields: dict[str, str]) -> str:
    """Substitute every ``{{key}}`` in one pass. Each placeholder is consumed
    exactly once, so a field value that itself contains ``{{token}}`` stays
    literal instead of being re-substituted."""
    return _TOKEN.sub(lambda m: str(fields.get(m.group(1), m.group(0))), template)


# --- sync state --------------------------------------------------------------

def load_state(out_dir: Path, state_file: str, defaults: dict) -> dict:
    """Load the sync-state JSON, tolerating a missing, corrupt, or
    schema-shifted file: every key in ``defaults`` is guaranteed present with
    the right type."""
    state: dict = {}
    path = out_dir / state_file
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except (ValueError, OSError):
            pass
    state.setdefault("version", 1)
    for key, default in defaults.items():
        if not isinstance(state.get(key), type(default)):
            # Copy — installing the caller's default object itself would let
            # one sync's mutations leak into every later "fresh" state.
            state[key] = copy.deepcopy(default)
    return state


def save_state(out_dir: Path, state_file: str, state: dict) -> None:
    """Write the sync state atomically so an interrupt can't leave a partial
    file that would silently reset all dedup history."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / (state_file + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(out_dir / state_file)
