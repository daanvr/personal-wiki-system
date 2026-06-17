#!/usr/bin/env python3
"""Email block — ingest mail into the wiki over IMAP (read-only).

On Windows use the ``py`` launcher (plain ``python`` is the Store stub):

    py ingest.py check                 # connect, authenticate, list folders + counts
    py ingest.py sync                  # fetch new mail and write notes
    py ingest.py sync --dry-run        # show what would be written, write nothing
    py ingest.py sync --folder INBOX   # restrict to one folder
    py ingest.py sync --limit 20       # cap messages per folder (handy for a first run)

Standard library only — no pip install required.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, imap, notes  # noqa: E402

STATE_FILE = ".sync-state.json"
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "email-note.md"


# --- helpers ---------------------------------------------------------------

def _excluded(folder: imap.Folder, excludes: set[str]) -> bool:
    if not excludes:
        return False
    name = folder.name.lower()
    if name in excludes:
        return True
    sep = folder.delimiter or "/"
    return any(seg.lower() in excludes for seg in folder.name.split(sep))


def scope_folders(conn, account, only=None) -> list[imap.Folder]:
    folders = imap.list_folders(conn)
    excludes = {x.strip().lower() for x in account.get("EXCLUDE_FOLDERS", "").split(",") if x.strip()}
    spec = account.get("FOLDERS", "ALL").strip()
    if only:
        folders = [f for f in folders if f.name == only]
    elif spec.upper() != "ALL":
        wanted = {x.strip() for x in spec.split(",") if x.strip()}
        folders = [f for f in folders if f.name in wanted]
    return [f for f in folders if not _excluded(f, excludes)]


def load_state(out_dir: Path) -> dict:
    path = out_dir / STATE_FILE
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"version": 1, "folders": {}, "message_ids": []}


def save_state(out_dir: Path, state: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")


# --- commands --------------------------------------------------------------

def cmd_check(account, provider) -> int:
    password = config.get_secret(account)
    print(f"Connecting to {provider.get('IMAP_HOST')}:{provider.get('IMAP_PORT')} "
          f"as {account['ACCOUNT']} ...")
    conn = imap.connect(account, provider, password)
    try:
        print("Authenticated OK.\n")
        excludes = {x.strip().lower() for x in account.get("EXCLUDE_FOLDERS", "").split(",") if x.strip()}
        in_scope = {f.name for f in scope_folders(conn, account)}
        print(f"{'':2} {'messages':>8}  folder")
        print("-" * 40)
        for f in imap.list_folders(conn):
            st = imap.folder_status(conn, f.name)
            mark = "*" if f.name in in_scope else (" " if not _excluded(f, excludes) else "x")
            print(f"{mark:2} {st['messages']:>8}  {f.name}")
        print("\n  * = in sync scope   x = excluded   (blank = not selected by FOLDERS)")
    finally:
        conn.logout()
    return 0


def cmd_sync(account, provider, dry_run: bool, only: str | None, limit: int | None) -> int:
    password = config.get_secret(account)
    out_dir = config.knowledge_path() / "sources" / account.get("OUTPUT_SUBDIR", "email")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    save_attachments = config.truthy(account.get("SAVE_ATTACHMENTS", "true"))

    state = load_state(out_dir)
    seen_ids = set(state.get("message_ids", []))

    conn = imap.connect(account, provider, password)
    written = skipped = 0
    try:
        folders = scope_folders(conn, account, only=only)
        if not folders:
            print("No folders in scope. Check FOLDERS / EXCLUDE_FOLDERS in config.")
            return 1
        print(f"Output: {out_dir}{'  (dry run — nothing will be written)' if dry_run else ''}\n")

        for folder in folders:
            fstate = state["folders"].get(folder.name, {})
            uidvalidity = imap.folder_status(conn, folder.name)["uidvalidity"]
            since = fstate.get("last_uid", 0)
            if fstate.get("uidvalidity") != uidvalidity:
                since = 0  # server renumbered UIDs — re-scan (dedup by Message-ID)

            imap.select_readonly(conn, folder.name)
            uids = imap.search_uids(conn, since)
            if limit:
                uids = uids[:limit]
            print(f"{folder.name}: {len(uids)} message(s) to consider")

            highest = since
            for uid in uids:
                highest = max(highest, uid)
                raw = imap.fetch_raw(conn, uid)
                if not raw:
                    continue
                msg = notes.parse_message(raw)
                mid = notes.header(msg, "message-id")
                if mid and mid in seen_ids:
                    skipped += 1
                    continue

                rel = notes.folder_subpath(folder.name, folder.delimiter)
                fname = notes.note_filename(
                    notes.message_date(msg), notes.header(msg, "subject"), mid
                )
                note_path = out_dir / rel / fname
                if note_path.exists():
                    if mid:
                        seen_ids.add(mid)
                    skipped += 1
                    continue

                attachments = notes.extract_attachments(msg) if save_attachments else []
                content = notes.render(template, msg, folder.name, [n for n, _ in attachments])

                if dry_run:
                    print(f"  would write {note_path.relative_to(out_dir)}")
                else:
                    note_path.parent.mkdir(parents=True, exist_ok=True)
                    note_path.write_text(content, encoding="utf-8")
                    if attachments:
                        att_dir = note_path.parent / "attachments" / fname[:-3]
                        att_dir.mkdir(parents=True, exist_ok=True)
                        for att_name, data in attachments:
                            (att_dir / att_name).write_bytes(data)
                    if mid:
                        seen_ids.add(mid)
                written += 1

            if not dry_run:
                state["folders"][folder.name] = {"uidvalidity": uidvalidity, "last_uid": highest}

        if not dry_run:
            state["message_ids"] = sorted(seen_ids)
            save_state(out_dir, state)
    finally:
        conn.logout()

    verb = "Would write" if dry_run else "Wrote"
    print(f"\n{verb} {written} note(s); skipped {skipped} already-ingested.")
    return 0


# --- entry point -----------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Ingest mail into the wiki (read-only IMAP).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="connect, authenticate, and list folders with counts")
    p_sync = sub.add_parser("sync", help="fetch new mail and write notes")
    p_sync.add_argument("--dry-run", action="store_true", help="show what would happen; write nothing")
    p_sync.add_argument("--folder", help="restrict to a single folder by exact name")
    p_sync.add_argument("--limit", type=int, help="max messages per folder this run")
    args = parser.parse_args(argv)

    account = config.load_account()
    provider = config.load_provider(account["PROVIDER"])

    if args.command == "check":
        return cmd_check(account, provider)
    return cmd_sync(account, provider, args.dry_run, args.folder, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
