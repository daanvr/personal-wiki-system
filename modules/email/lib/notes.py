"""Turn a fetched RFC822 message into a Markdown wiki note.

Output is Obsidian-friendly: YAML frontmatter plus a Markdown body, written
into the private knowledge base. De-duplication is by ``Message-ID`` so
re-running sync never creates duplicate notes.
"""
from __future__ import annotations

import email
import email.policy
import hashlib
import html
import re
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from _shared import wikilib


# --- message parsing -------------------------------------------------------

def parse_message(raw: bytes):
    return email.message_from_bytes(raw, policy=email.policy.default)


def header(msg, name: str) -> str:
    val = msg[name]
    return str(val).strip() if val else ""


def message_date(msg):
    """Parsed ``datetime`` from the Date header, or ``None`` if absent/bad."""
    if not msg["date"]:
        return None
    try:
        return parsedate_to_datetime(msg["date"])
    except (TypeError, ValueError):
        return None


class _HTMLToText(HTMLParser):
    _BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html)
    text = "".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_body(msg) -> str:
    """Best-effort Markdown body: prefer text/plain, fall back to HTML."""
    plain = html_body = None
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        try:
            content = part.get_content()
        except (LookupError, UnicodeDecodeError):
            # Charset Python has no codec for — decode leniently rather than
            # silently writing an empty body.
            payload = part.get_payload(decode=True) or b""
            content = payload.decode("utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/plain" and plain is None:
            plain = content
        elif ctype == "text/html" and html_body is None:
            html_body = content
    if plain is not None:
        # Some senders (e.g. Google Calendar) HTML-escape their plain-text
        # part, so unescape entities here too — _html_to_text already decodes
        # them on the HTML path.
        return html.unescape(plain).strip()
    if html_body is not None:
        return _html_to_text(html_body)
    return ""


def extract_attachments(msg) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    seen: dict[str, int] = {}
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        name = wikilib.safe_name(part.get_filename() or "attachment")
        n = seen.get(name, 0)
        seen[name] = n + 1
        if n:
            stem, dot, ext = name.rpartition(".")
            name = f"{stem}-{n}.{ext}" if dot else f"{name}-{n}"
        out.append((name, payload))
    return out


# --- naming / paths --------------------------------------------------------

def folder_subpath(folder_name: str, delimiter: str) -> Path:
    sep = delimiter or "/"
    parts = [wikilib.safe_name(p) for p in folder_name.split(sep) if p]
    return Path(*parts) if parts else Path("INBOX")


def note_filename(date, subject: str, message_id: str, msg=None) -> str:
    datestr = date.strftime("%Y-%m-%d") if date else "undated"
    slug = wikilib.slugify(subject) or "no-subject"
    if message_id:
        source = message_id
    else:
        # No Message-ID: derive the digest from stable message content so two
        # different mails with the same subject and day don't collide.
        sender = header(msg, "from") if msg is not None else ""
        body = extract_body(msg)[:512] if msg is not None else ""
        source = f"{sender}|{date.isoformat() if date else ''}|{subject}|{body}"
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:8]
    return f"{datestr} {slug} {digest}.md"


# --- rendering -------------------------------------------------------------

def render(template: str, msg, folder_name: str, attachment_names: list[str]) -> str:
    date = message_date(msg)

    if attachment_names:
        links = "\n".join(f"- `{n}`" for n in attachment_names)
        attachments_block = f"\n**Attachments:**\n{links}\n"
    else:
        attachments_block = ""

    fields = {
        "subject": wikilib.yaml_escape(header(msg, "subject")) or "(no subject)",
        "from": wikilib.yaml_escape(header(msg, "from")),
        "to": wikilib.yaml_escape(header(msg, "to")),
        "cc": wikilib.yaml_escape(header(msg, "cc")),
        "date_iso": date.isoformat() if date else "",
        "date_human": date.strftime("%a, %d %b %Y %H:%M") if date else "unknown",
        "message_id": wikilib.yaml_escape(header(msg, "message-id")),
        "folder": wikilib.yaml_escape(folder_name),
        "attachments_block": attachments_block,
        "body": extract_body(msg),
    }
    return wikilib.render_template(template, fields)
