#!/usr/bin/env python3
"""Calendar module — ingest CalDAV events into the wiki (read-only).

Run with Python 3. Use ``python3`` on macOS/Linux, or the ``py`` launcher on
Windows (where plain ``python`` is the Microsoft Store stub):

    python3 ingest.py check
    python3 ingest.py sync --dry-run
    python3 ingest.py sync --days-back 30 --days-forward 365
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import caldav_client, config, events  # noqa: E402
from _shared import wikilib  # noqa: E402

STATE_FILE = ".sync-state.json"
STATE_DEFAULTS = {"events": {}}
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "calendar-event.md"


def _excluded(name: str, excludes: set[str]) -> bool:
    return name.lower() in excludes


def _scope_calendars(calendars: list[object], account: dict[str, str], only: str | None = None) -> list[object]:
    excludes = {
        x.strip().lower()
        for x in account.get("EXCLUDE_CALENDARS", "").split(",")
        if x.strip()
    }
    spec = account.get("CALENDARS", "ALL").strip()
    wanted = {x.strip().lower() for x in spec.split(",") if x.strip()}
    out = []
    for calendar in calendars:
        name = caldav_client.calendar_name(calendar)
        if only:
            # An explicitly requested calendar is never filtered by the
            # exclude list.
            if name == only:
                out.append(calendar)
            continue
        if spec.upper() != "ALL" and name.lower() not in wanted:
            continue
        if _excluded(name, excludes):
            continue
        out.append(calendar)
    return out


def _window(account: dict[str, str], days_back: int | None, days_forward: int | None) -> tuple[datetime, datetime]:
    back = days_back if days_back is not None else config.get_int(account, "DAYS_BACK", 30)
    forward = days_forward if days_forward is not None else config.get_int(account, "DAYS_FORWARD", 365)
    now = datetime.now(timezone.utc)
    return now - timedelta(days=back), now + timedelta(days=forward)


def load_state(out_dir: Path) -> dict:
    return wikilib.load_state(out_dir, STATE_FILE, STATE_DEFAULTS)


def save_state(out_dir: Path, state: dict) -> None:
    wikilib.save_state(out_dir, STATE_FILE, state)


def cmd_check(account: dict[str, str], provider: dict[str, str]) -> int:
    password = config.get_secret(account)
    url = provider["CALDAV_URL"]
    print(f"Connecting to {url} as {account['ACCOUNT']} ...")
    with caldav_client.connect(url, account["ACCOUNT"], password) as client:
        calendars = caldav_client.list_calendars(client)
        in_scope = {caldav_client.calendar_name(c) for c in _scope_calendars(calendars, account)}
        print("Authenticated OK.\n")
        print(f"{'':2} calendar")
        print("-" * 60)
        for calendar in calendars:
            name = caldav_client.calendar_name(calendar)
            mark = "*" if name in in_scope else " "
            print(f"{mark:2} {name}")
        print("\n  * = in sync scope")
    return 0


def cmd_sync(
    account: dict[str, str],
    provider: dict[str, str],
    dry_run: bool,
    only: str | None,
    days_back: int | None,
    days_forward: int | None,
) -> int:
    password = config.get_secret(account)
    out_dir = config.knowledge_path() / "sources" / account.get("OUTPUT_SUBDIR", "calendar")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    start, end = _window(account, days_back, days_forward)
    state = load_state(out_dir)

    written = updated = skipped = 0
    print(
        f"Output: {out_dir}{'  (dry run - nothing will be written)' if dry_run else ''}\n"
        f"Window: {start.isoformat()} to {end.isoformat()}\n"
    )

    with caldav_client.connect(provider["CALDAV_URL"], account["ACCOUNT"], password) as client:
        calendars = _scope_calendars(caldav_client.list_calendars(client), account, only=only)
        if not calendars:
            print("No calendars in scope. Check CALENDARS / EXCLUDE_CALENDARS in config.")
            return 1

        for calendar in calendars:
            cal_name = caldav_client.calendar_name(calendar)
            cal_url = caldav_client.calendar_url(calendar)
            resources = caldav_client.search_events(calendar, start, end)
            print(f"{cal_name}: {len(resources)} resource(s) to consider")

            for resource in resources:
                # One unreadable or unparsable resource must not abort the
                # run (Calendar.from_ical raises on malformed payloads).
                try:
                    raw = caldav_client.resource_data(resource)
                    resource_url = caldav_client.resource_url(resource)
                    etag = caldav_client.resource_etag(resource)
                    components = events.parse_events(raw)
                except Exception as exc:
                    print(f"  ! skipped an unreadable resource in {cal_name}: {exc}")
                    continue
                for component in components:
                    try:
                        key = events.event_key(cal_url, component)
                        previous = state["events"].get(key, {})
                        rel = previous.get("path")
                        if not rel:
                            rel = str(
                                events.calendar_subpath(cal_name)
                                / events.note_filename(cal_url, component)
                            )
                        note_path = out_dir / rel
                        # An empty ETag means the server doesn't report one;
                        # treat as "unknown" and re-render rather than skip
                        # forever.
                        if etag and previous.get("etag") == etag and note_path.exists():
                            skipped += 1
                            continue

                        content = events.render(template, component, cal_name, cal_url, resource_url)
                        action = "update" if note_path.exists() else "write"
                        if dry_run:
                            print(f"  would {action} {note_path.relative_to(out_dir)}")
                        else:
                            note_path.parent.mkdir(parents=True, exist_ok=True)
                            note_path.write_text(content, encoding="utf-8")
                            state["events"][key] = {
                                "path": rel,
                                "etag": etag,
                                "calendar": cal_name,
                                "calendar_url": cal_url,
                                "resource_url": resource_url,
                            }
                        if action == "update":
                            updated += 1
                        else:
                            written += 1
                    except Exception as exc:
                        print(f"  ! skipped a malformed event in {cal_name}: {exc}")
                        continue

            if not dry_run:
                # Persist per calendar so a failure later in the run doesn't
                # discard the progress already made.
                save_state(out_dir, state)

    verb = "Would write" if dry_run else "Wrote"
    print(f"\n{verb} {written} note(s); updated {updated}; skipped {skipped} unchanged.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Ingest CalDAV events into the wiki (read-only).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="connect, authenticate, and list calendars")
    p_sync = sub.add_parser("sync", help="fetch events and write notes")
    p_sync.add_argument("--dry-run", action="store_true", help="show what would happen; write nothing")
    p_sync.add_argument("--calendar", help="restrict to a single calendar by exact name")
    p_sync.add_argument("--days-back", type=int, help="override DAYS_BACK from config")
    p_sync.add_argument("--days-forward", type=int, help="override DAYS_FORWARD from config")
    args = parser.parse_args(argv)

    account = config.load_account()
    provider = config.load_provider(account["PROVIDER"])

    if args.command == "check":
        return cmd_check(account, provider)
    return cmd_sync(
        account,
        provider,
        args.dry_run,
        args.calendar,
        args.days_back,
        args.days_forward,
    )


if __name__ == "__main__":
    raise SystemExit(main())
