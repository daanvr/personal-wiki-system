# Personal Wiki System

The **system** half of a personal wiki project — the tooling, structure, and conventions
that power a personal knowledge base. It contains no personal data, so it can be shared
and worked on openly.

## Two-repository design

This project is deliberately split into two repositories that are kept strictly separate:

- **`system`** (this repo, public) — the engine: tooling, structure, conventions,
  templates, and automation. Nothing personal lives here.
- **`knowledge`** (separate, private) — the data: source material and an Obsidian-style
  wiki built from it. This stays private.

Keeping the system and the data apart means the system can be public and reusable while
the knowledge it organizes remains private.

```
personal-wiki-system/
├── system/      ← this repository (public)
└── knowledge/   ← separate private repository
```

## Requirements

The tooling is cross-platform (macOS, Linux, Windows):

- **Shell scripts** (`init.sh` and friends) are Bash. They run natively on
  macOS/Linux; on Windows run them under **Git Bash** or **WSL**
  (e.g. `bash init.sh`).
- **Python 3** for modules that need it. Some modules are standard-library
  only; others have a module-local `requirements.txt`. Invoke Python as
  `python3` on macOS/Linux, or via the `py` launcher on Windows (plain
  `python` there is the Microsoft Store stub).

## Getting started

Run the setup wizard:

```sh
./init.sh                 # interactive: scaffold + guided module setup
./init.sh /path/to/kb     # put the knowledge base somewhere specific
```

The wizard scaffolds the knowledge base (`sources/`, `wiki/`, `settings/`), then offers
each available module (email, calendar, ...) and walks you through configuring it:
provider selection, app-password instructions, per-field prompts, and a live connection
check at the end — so setup finishes with a proven-working integration. Re-run it any
time; it is idempotent and pre-fills your existing answers.

Non-interactive variants:

```sh
./init.sh --list          # show modules + status
./init.sh --with email    # set up specific modules
./init.sh --all-modules   # everything available
./init.sh --no-modules    # base scaffold only
./init.sh --yes           # accept defaults, scaffold configs to edit by hand
```

Print the resolved knowledge-base path any time with:

```sh
./knowledge-path.sh
```

## Configuration

Two kinds of config, in two places:

- **`config` in this repo** (gitignored, per machine) holds only the bootstrap pointer:
  `KNOWLEDGE_PATH`, absolute or relative to this repo's root (e.g. `../knowledge`).
- **Your module settings live in the knowledge repo** at
  `<knowledge>/settings/modules/<module>/config`. They contain personal data (your
  email address, folder choices), so they belong in the **private** repo — versioned
  and backed up there, and they survive re-cloning this system repo. Passwords are
  never stored in them: each module resolves its secret from an environment variable
  (`SECRET_REF`), or from a gitignored `secret` file the wizard can write next to the
  config.

Each module keeps its committed `config.example` (the template and documentation) and
`providers/*.conf` profiles here in the system repo. See
[docs/setup-wizard.md](docs/setup-wizard.md) for how modules describe themselves to the
wizard.

## Status

Config, the setup wizard, and the first two ingestion modules (email over IMAP,
calendar over CalDAV — both read-only) are in place; wiki structure and conventions
are still to be designed.
