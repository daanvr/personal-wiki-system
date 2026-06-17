# Proposal: a modular installer for the wiki system

**Status:** Draft for discussion · **Date:** 2026-06-17

## Context

The system repo will accumulate optional "puzzle pieces" (modules) over time —
the first being the `email` module. We want `init.sh` to set up the project and
let the user opt into modules and configure them, **without** the installer
turning into a sprawl of per-module `if`-statements as more modules land.

This document proposes how to structure that, for the team to discuss before we
implement.

## TL;DR — recommendation

Make `init.sh` a **dumb, convention-driven installer**: it understands a
*contract* for what a module is, and never names a specific module. Each module
is a self-contained, self-describing folder. Adding or removing a module never
touches `init.sh`, so the installer stays a constant size as modules accumulate.

## The contract — what makes a "module"

A module is any `modules/<name>/` folder containing:

| File | Purpose |
| --- | --- |
| `module.conf` | Manifest (`title`, `description`, optional `requires`). Parsed — never executed — to build the menu. |
| `config.example` | Config template (committed). |
| `setup.sh` | The module's own setup, run when the user enables it. Idempotent. |

**"Enabled" = the module has a `config` file.** State is derived from the
filesystem; there is no central registry to keep in sync.

This is the same self-describing-folder convention the `email` module already
follows (provider profiles, `config.example` → gitignored `config`, secret by
reference) — lifted up to the installer level.

## How `init.sh` would behave

1. Base setup (knowledge repo + root config) — unchanged from today.
2. Discover `modules/*/module.conf`.
3. Offer each not-yet-enabled module; on "yes," run that module's `setup.sh`.

Plus non-interactive flags for scripting/CI:

```
./init.sh --with email      # enable specific modules
./init.sh --all-modules     # enable everything available
./init.sh --no-modules      # base setup only
./init.sh --list            # show modules + status, no setup
```

Sketch of the interactive flow:

```
Setting up knowledge base
  ... base setup ...

Optional modules:

  Email - Pull email into the wiki over IMAP (read-only).
  Enable? [y/N] y
    -> runs modules/email/setup.sh (scaffolds config, prints next steps)

  (the next module appears here automatically - no init.sh changes)
```

## Why it won't bloat

| Concern | How the design handles it |
| --- | --- |
| `init.sh` growing per module | Constant size; it iterates a contract |
| Modules entangled | Each is a drop-in / removable folder (`rm -rf modules/x`) |
| Config sprawl | One `KEY=value` + `config.example` → `config` convention everywhere |
| Tracking what's enabled | Derived from `config` presence — nothing to maintain |
| Secrets | Each module guides its own; never centralized or stored |

## Proposed defaults (open to revisit)

- **Installer UX:** interactive menu *and* flags.
- **Mail setup depth:** scaffold-only — copy the template and print what to fill
  in and which env var to set, rather than per-field prompts.

## Trade-offs & alternatives considered

- **Manifest format:** reuse `KEY=value` for consistency with the rest of the
  repo. Alternative (TOML/JSON) adds a parser dependency — rejected for now.
- **Per-module `setup.sh` vs. a fully declarative manifest:** a script is more
  flexible (secret guidance, optional verification) at the cost of a little code
  per module. Declarative-only would be cleaner but can't express
  guidance/validation well.
- **Extend `init.sh` vs. a separate `modules.sh` command:** leaning toward
  extending (one entry point). A separate command gives more separation but adds
  another thing to learn.

## Open questions for the team

1. **Installer language.** The repo is Bash, but the project is
   **Windows-primary** (Bash needs Git Bash/WSL; the email engine already uses
   Python via the `py` launcher). Should the installer stay Bash, or move to
   **Python** to match the runtime and simplify cross-platform support? *(Biggest
   strategic question.)*
2. **Disable / teardown.** "Enabled = has config" has no first-class *disable*
   (you'd delete `config`). Do we want an explicit `--disable` or richer status?
3. **`requires` enforcement.** Informational only as proposed. Should the
   installer hard-block when a dependency (e.g. Python 3) is missing?
4. **Naming.** Module dir is `email`; the flag would be `--with email`. We've
   been saying "mail" colloquially — alias, or rename?
5. **Cross-module secret convention.** Standardize the env-var / keychain pattern
   now so module #2 and #3 don't each reinvent it.

## Notes

A partial reference implementation of this design was prototyped and then
reverted, pending this discussion. Re-creating it is straightforward once the
open questions above are settled.
