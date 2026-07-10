# Calendar module

Pull calendar events into the knowledge base as Markdown notes.

It is built around **standard CalDAV**, not a single provider. The engine
speaks CalDAV; each calendar service is just a small **provider profile**. So
the same code can ingest Cirrux, Fastmail, Nextcloud, Radicale, SOGo, or any
other CalDAV-capable service.

## How it's layered

| Layer | Where | Public? |
| --- | --- | --- |
| Transport (CalDAV, read-only) | `lib/caldav_client.py` | public |
| Provider profile (base URL/auth) | `providers/<name>.conf` | **public** — no secrets |
| Account config | `<knowledge>/settings/modules/calendar/config` | **private** (knowledge repo) |
| Password | env var (`SECRET_REF`) or gitignored `secret` file | **never committed anywhere** |
| Event → note rendering | `lib/events.py`, `templates/calendar-event.md` | public |
| The notes themselves | `<knowledge>/sources/<subdir>/` | **private** (separate repo) |

Nothing personal lives in this repo. The account config (it contains your
address) lives in the **private** knowledge repo; the password is resolved at
runtime from an environment variable (or a gitignored file); the ingested
calendar notes are written into the knowledge repo too.

## Setup

**Run the setup wizard** from the system repo root — it checks this module's
Python dependencies (offering to `pip install` them), walks you through
provider, account, calendars, and the password, then verifies the connection
live:

```sh
./init.sh                # or: ./init.sh --with calendar
```

Requires Python 3.9+. Invoke Python as `python3` on macOS/Linux, or via the
`py` launcher on Windows (plain `python` there is the Microsoft Store stub).

<details>
<summary>Manual setup (what the wizard does for you)</summary>

1. Install this module's dependencies:
   ```sh
   # macOS / Linux                      # Windows (PowerShell)
   cd modules/calendar                  # cd modules/calendar
   python3 -m pip install -r requirements.txt   # py -m pip install -r requirements.txt
   ```

2. Copy `config.example` to `<knowledge>/settings/modules/calendar/config` and
   fill it in: set `ACCOUNT` to your address and confirm `PROVIDER=cirrux`.

3. Provide the password without committing it: generate a Cirrux app-specific
   password if available, then expose it via the env var named in `SECRET_REF`
   (default `CIRRUX_APP_PASSWORD`):
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
python3 ingest.py check
python3 ingest.py sync --dry-run
python3 ingest.py sync --days-back 30 --days-forward 365
python3 ingest.py sync
```

`check` is the thing to run first — it proves the connection and credentials
and shows which calendars are in scope, before anything is written.

## What sync does

- Reads every in-scope calendar (`CALENDARS` / `EXCLUDE_CALENDARS` in
  `config`), **read-only**.
- Searches a bounded time window (`DAYS_BACK` / `DAYS_FORWARD`) so the first run
  does not fetch a lifetime of historical events.
- Writes one Markdown note per `VEVENT` into
  `<knowledge>/sources/<OUTPUT_SUBDIR>/<calendar>/`, with YAML frontmatter.
- Tracks local paths and ETags in `.sync-state.json` beside the notes, so
  unchanged resources are skipped and updated resources overwrite the same note.

## Adding another provider later

The wizard's "Other..." choice creates one for you (stored privately in
`<knowledge>/settings/modules/calendar/providers/`). Or by hand: copy
`providers/_template.conf` to `providers/<name>.conf`, fill in the CalDAV
base URL, and set `PROVIDER=<name>` in your config. No code changes — and a
good profile can be promoted into this repo for everyone.

## Current limitations

- Read-only. It never creates, updates, or deletes server-side events.
- Deleted server-side events are not removed locally yet.
- Recurring events are stored as the server returns them. This first pass does
  not expand recurring series into separate occurrence notes.
- Authentication currently assumes username + password over HTTPS.
