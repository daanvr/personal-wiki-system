# Email module

The first "puzzle piece" of the wiki system: pull email into the knowledge
base as Markdown notes.

It is built around **standard IMAP**, not any single provider. The engine
speaks IMAP; each mail service is just a small **provider profile**. So the
same code ingests Cirrux, Fastmail, Gmail, a self-hosted server — anything
that offers IMAP. Adding a provider is adding one config file, not new code.

## How it's layered

| Layer | Where | Public? |
| --- | --- | --- |
| Transport (IMAP, read-only) | `lib/imap.py` | public |
| Provider profile (host/port/auth) | `providers/<name>.conf` | **public** — no secrets |
| Account config | `<knowledge>/settings/modules/email/config` | **private** (knowledge repo) |
| Password | env var (`SECRET_REF`) or gitignored `secret` file | **never committed anywhere** |
| Message → note rendering | `lib/notes.py`, `templates/email-note.md` | public |
| The notes themselves | `<knowledge>/sources/<subdir>/` | **private** (separate repo) |

Nothing personal lives in this repo. The account config (it contains your
address) lives in the **private** knowledge repo; the password is resolved at
runtime from an environment variable (or a gitignored file); the ingested mail
is written into the knowledge repo too.

## Setup

**Run the setup wizard** from the system repo root — it walks you through
provider, account, folders, and the password, then verifies the connection
live:

```sh
./init.sh                # or: ./init.sh --with email
```

Requires Python 3 (standard library only for this module — no `pip install`).
Invoke Python as `python3` on macOS/Linux, or the `py` launcher on Windows
(plain `python` there is the Microsoft Store stub).

<details>
<summary>Manual setup (what the wizard does for you)</summary>

1. Copy `config.example` to `<knowledge>/settings/modules/email/config` and
   fill it in: set `ACCOUNT` to your address and confirm `PROVIDER=cirrux`.

2. Provide the password without committing it: generate a Cirrux
   *app-specific password*, then expose it via the env var named in
   `SECRET_REF` (default `CIRRUX_APP_PASSWORD`):
   ```sh
   # macOS / Linux (current shell)
   export CIRRUX_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
   ```
   ```powershell
   # Windows (PowerShell, current session)
   $env:CIRRUX_APP_PASSWORD = "xxxx-xxxx-xxxx-xxxx"
   ```
   Or put it in a file named `secret` next to that config (gitignored there)
   and set `SECRET_FILE=secret`.
</details>

## Usage

Use `python3` on macOS/Linux (or `py` on Windows):

```sh
python3 ingest.py check            # connect, authenticate, list folders + counts
python3 ingest.py sync --dry-run   # show what would be written, write nothing
python3 ingest.py sync --limit 20  # first real run, capped per folder
python3 ingest.py sync             # full incremental sync
```

`check` is the thing to run first — it proves the connection and credentials
and shows which folders are in scope, before anything is written.

## What sync does

- Reads every in-scope folder (`FOLDERS` / `EXCLUDE_FOLDERS` in `config`),
  **read-only** — it never marks mail as read or changes the server.
- Writes one Markdown note per message into
  `<knowledge>/sources/<OUTPUT_SUBDIR>/<folder>/`, with YAML frontmatter
  (subject, from/to/cc, date, message-id, folder) and the body as text.
- De-duplicates by `Message-ID`, and tracks each folder's last UID in a
  `.sync-state.json` beside the notes — so re-running only fetches new mail
  and never creates duplicates.

## Adding another provider later

The wizard's "Other..." choice creates one for you (stored privately in
`<knowledge>/settings/modules/email/providers/`). Or by hand: copy
`providers/_template.conf` to `providers/<name>.conf`, fill in the IMAP
host/port, and set `PROVIDER=<name>` in your config. No code changes — and a
good profile can be promoted into this repo for everyone.

## Current limitations

- Read-only (no sending). SMTP fields in the provider profile are reserved.
- HTML-only emails are converted to plain text with a minimal stdlib parser;
  formatting is approximate.
- Non-ASCII (modified-UTF-7) IMAP folder names pass through unconverted.
