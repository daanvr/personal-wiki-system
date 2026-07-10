"""The secret sub-flow: how the module finds the account password.

Two choices, matching the runtime contract in ``wikilib.get_secret``:

- **Environment variable** (recommended): the config stores only the variable
  name (``SECRET_REF``); the wizard can take the value once, in memory, so the
  live verification can run — it is never written to disk.
- **Secret file**: written next to the module's config in the knowledge repo,
  ``chmod 0600`` (best-effort on Windows), gitignored there.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from . import manifest

SECRET_FILENAME = "secret"


def configure(io, module: manifest.Module, knowledge: Path,
              defaults: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Returns (config updates, runtime-only env for verification)."""
    ref_default = defaults.get("SECRET_REF", "APP_PASSWORD")
    method = io.select(
        "How should the password be provided at runtime?",
        [
            ("env", "Environment variable (recommended)",
             "config stores only the variable name; the secret never touches disk"),
            ("file", "Secret file",
             "stored next to this module's config in the knowledge repo, gitignored"),
        ],
        default="env",
    )

    if method == "env":
        name = io.ask("Environment variable name", default=ref_default)
        io.info("")
        io.info("Set it in your shell before running a sync:")
        io.info(f'  macOS/Linux:          export {name}="xxxx-xxxx-xxxx-xxxx"')
        io.info(f'  Windows (PowerShell): $env:{name} = "xxxx-xxxx-xxxx-xxxx"')
        io.info("")
        runtime_env: dict[str, str] = {}
        if os.environ.get(name):
            io.info(f"({name} is already set in this session — it will be used to verify.)")
        else:
            value = io.secret("Paste the app password now to verify the connection "
                              "(kept in memory only; Enter to skip)")
            if value:
                runtime_env[name] = value
        return {"SECRET_REF": name}, runtime_env

    value = io.secret("App password")
    secret_path = manifest.settings_dir(module, knowledge) / SECRET_FILENAME
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(value + "\n", encoding="utf-8")
    try:
        secret_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # chmod is best-effort on Windows
    io.info(f"Wrote {secret_path} (gitignored, owner-only permissions)")
    # SECRET_REF stays set: an env var, when present, still takes precedence.
    return {"SECRET_REF": ref_default, "SECRET_FILE": SECRET_FILENAME}, {}
