"""A thin IMAP layer over the standard-library ``imaplib``.

Read-only by design: mailboxes are always selected with ``readonly=True`` so
ingesting mail never changes ``\\Seen`` flags or anything else on the server.
"""
from __future__ import annotations

import imaplib
import re
from dataclasses import dataclass

from . import config

# Matches a LIST response line: (flags) "delim" name
_LIST_RE = re.compile(rb'^\((?P<flags>[^)]*)\) (?P<delim>"[^"]*"|NIL) (?P<name>.*)$')
# Matches the "(...)" payload of a STATUS response.
_STATUS_RE = re.compile(rb"\(([^)]*)\)\s*$")


@dataclass
class Folder:
    name: str        # raw IMAP name, e.g. "INBOX" or "Archive/2025"
    flags: str
    delimiter: str


def connect(account: dict, provider: dict, password: str) -> imaplib.IMAP4:
    host = provider.get("IMAP_HOST")
    if not host:
        raise SystemExit("Provider profile is missing IMAP_HOST.")
    port = int(provider.get("IMAP_PORT", "993"))
    if config.truthy(provider.get("IMAP_SSL", "true")):
        conn: imaplib.IMAP4 = imaplib.IMAP4_SSL(host, port)
    else:
        conn = imaplib.IMAP4(host, port)
    conn.login(account["ACCOUNT"], password)
    return conn


def _quote(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _decode_name(raw: bytes) -> str:
    # latin-1 is lossless for bytes and identical to ASCII for plain names.
    # Modified-UTF-7 (non-ASCII) folder names pass through unchanged for now.
    text = raw.decode("latin-1").strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return text


def list_folders(conn: imaplib.IMAP4) -> list[Folder]:
    typ, data = conn.list()
    folders: list[Folder] = []
    if typ != "OK":
        return folders
    for raw in data:
        if raw is None:
            continue
        if isinstance(raw, tuple):
            raw = b" ".join(raw)
        m = _LIST_RE.match(raw)
        if not m:
            continue
        flags = m.group("flags").decode()
        if "\\Noselect" in flags:  # containers that hold no messages
            continue
        delim = m.group("delim").decode().strip('"')
        if delim == "NIL" or not delim:
            delim = "/"
        folders.append(
            Folder(name=_decode_name(m.group("name")), flags=flags, delimiter=delim)
        )
    return folders


def folder_status(conn: imaplib.IMAP4, name: str) -> dict:
    """Return {messages, uidnext, uidvalidity} without selecting the box."""
    res = {"messages": 0, "uidnext": 0, "uidvalidity": 0}
    typ, data = conn.status(_quote(name), "(MESSAGES UIDNEXT UIDVALIDITY)")
    if typ != "OK" or not data or not data[0]:
        return res
    m = _STATUS_RE.search(data[0] if isinstance(data[0], bytes) else data[0][0])
    if not m:
        return res
    tokens = m.group(1).split()
    pairs = dict(zip(tokens[0::2], tokens[1::2]))
    res["messages"] = int(pairs.get(b"MESSAGES", b"0"))
    res["uidnext"] = int(pairs.get(b"UIDNEXT", b"0"))
    res["uidvalidity"] = int(pairs.get(b"UIDVALIDITY", b"0"))
    return res


def select_readonly(conn: imaplib.IMAP4, name: str) -> None:
    typ, data = conn.select(_quote(name), readonly=True)
    if typ != "OK":
        raise RuntimeError(f"cannot select {name!r}: {data!r}")


def search_uids(conn: imaplib.IMAP4, since_uid: int = 0) -> list[int]:
    """UIDs in the selected folder; only those above ``since_uid`` if given."""
    criterion = f"UID {since_uid + 1}:*" if since_uid else "ALL"
    typ, data = conn.uid("search", None, criterion)
    if typ != "OK" or not data or not data[0]:
        return []
    return [int(x) for x in data[0].split()]


def fetch_raw(conn: imaplib.IMAP4, uid: int) -> bytes | None:
    typ, data = conn.uid("fetch", str(uid), "(RFC822)")
    if typ != "OK" or not data:
        return None
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2:
            return item[1]
    return None
