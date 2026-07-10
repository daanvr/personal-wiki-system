# The setup wizard and the module contract

**Status:** Implemented · supersedes [modular-installer-proposal.md](modular-installer-proposal.md)

`./init.sh` launches the setup wizard (`wizard.py`, Python 3 stdlib-only). It scaffolds
the knowledge base, migrates legacy configs, and offers each available module a guided,
live-verified setup. The wizard is **convention-driven**: it understands the contract
below and never names a specific module — adding or removing a module never touches the
wizard core.

## Where things live

| Thing | Where | Committed? |
| --- | --- | --- |
| Module manifest | `modules/<m>/module.conf` | yes (system repo) |
| Config template + docs | `modules/<m>/config.example` | yes (system repo) |
| Provider profiles | `modules/<m>/providers/*.conf` | yes (system repo) |
| **User account config** | `<knowledge>/settings/modules/<m>/config` | yes (**private** knowledge repo) |
| User provider profiles | `<knowledge>/settings/modules/<m>/providers/*.conf` | yes (private knowledge repo) |
| Secret file (optional) | `<knowledge>/settings/modules/<m>/secret` | **no — gitignored, 0600** |

**"Enabled" = the module has a config in the knowledge settings home.** State is
derived from the filesystem; there is no registry. Because settings live with the
private data, cloning both repos onto a new machine restores the full module setup
minus secrets.

The legacy location (`modules/<m>/config` in the system repo) still resolves as a
fallback with a deprecation warning; the wizard offers to migrate it.

## The module contract

A module is any `modules/<name>/` folder (not starting with `_`) containing a
`module.conf` manifest — KEY=value, **parsed, never executed**:

```
TITLE=Email                    # display name
DESCRIPTION=Pull email ...     # one-liner for the menu
CHECK=ingest.py check          # argv (relative to the module dir) for live verification
REQUIRES_PYTHON=3.9            # optional minimum Python version
PY_IMPORTS=caldav,icalendar    # optional third-party imports to probe
```

Everything else derives from files the module already maintains:

- **Prompts come from `config.example`.** Every `KEY=value` line becomes a prompt: the
  example value is the default, and the `#` comment block directly above the key is the
  help text (a blank line ends a block). A commented-out `# KEY=value` line marks an
  optional field. Keep templates in this shape and a new module gets a full guided
  setup with zero wizard changes.
- **Reserved keys.** `PROVIDER` triggers the provider picker; `SECRET_REF` /
  `SECRET_FILE` trigger the secret sub-flow. Everything else is a plain
  prompt-with-default.
- **Provider presentation keys** (optional, in `providers/*.conf`; ingest engines
  ignore unknown keys): `LABEL` (picker display name), `APP_PASSWORD_HINT` (shown
  before the password prompt — where to create one), `DOCS_URL`.
- **Dependencies.** If `PY_IMPORTS` names missing packages and the module ships a
  `requirements.txt`, the wizard offers to `pip install -r` it.
- **Verification.** After writing the config, the wizard runs `CHECK` as a subprocess
  (cwd = the module dir). A session-only secret travels via the environment, never on
  the command line. On failure the user can retry, re-enter the password, or keep the
  config anyway.

## Secrets policy

Secrets are never committed — not even to the private knowledge repo (it gets pushed,
git history makes rotation messy, and it is exactly what gets handed to other tooling).
The recommended method is an environment variable (config stores only its name in
`SECRET_REF`); the convenience option is a `secret` file the wizard writes next to the
module's config with owner-only permissions, covered by the knowledge repo's
`.gitignore` (`/settings/modules/*/secret`).

## Wizard architecture

```
wizard.py            entry point: argparse + ConsoleIO + engine.run()
lib/wizard/
  engine.py          orchestration; atomic config writes rendered from config.example
  base.py            knowledge-base scaffolding (idempotent; .gitignore append-only)
  manifest.py        module discovery + enabled state
  fields.py          config.example -> prompt specs; config rendering
  providers.py       provider listing/merging + custom-profile creation
  secrets.py         env-var vs secret-file sub-flow
  deps.py            python version + import probes + pip offer
  verify.py          runs the module's CHECK subprocess
  migrate.py         legacy-location detection and migration
  console.py         ALL interactive IO goes through this interface
```

`console.py` is the deliberate seam: no other wizard file reads the keyboard, so a
scripted front-end (the test suite's `ScriptedIO`) — or a future local web UI — swaps
in without touching setup logic.

An escape hatch exists for modules whose setup can't be expressed declaratively:
an optional `modules/<name>/setup_hooks.py` exposing `post_configure(ctx)` would be
imported by the engine only if present. No current module needs one, and the hook is
not wired up yet — add it when a module actually requires it.

## Tests

```sh
python3 -m unittest discover -s tests
```

Engine tests run against a synthetic module in a temp directory; parser tests run
against the real `config.example` files so comment-format drift fails loudly.
