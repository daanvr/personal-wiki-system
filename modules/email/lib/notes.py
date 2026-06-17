"""Turn a fetched RFC822 message into a Markdown wiki note.

Output is Obsidian-friendly: YAML frontmatter plus a Markdown body, written
into the private knowledge base. De-duplication is by ``Message-ID`` so
re-running sync never creates duplicate notes.
"""
from __future__ import annotations

import email
import email.policy
import hashlib
import re
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

_WIN_RESERVED = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


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
    plain = html = None
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        try:
            content = part.get_content()
        except Exception:
            continue
        if ctype == "text/plain" and plain is None:
            plain = content
        elif ctype == "text/html" and html is None:
            html = content
    if plain is not None:
        return plain.strip()
    if html is not None:
        return _html_to_text(html)
    return ""


def extract_attachments(msg) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        name = part.get_filename() or "attachment"
        payload = part.get_payload(decode=True)
        if payload:
            out.append((_safe_name(name), payload))
    return out


# --- naming / paths --------------------------------------------------------

def _safe_name(name: str) -> str:
    name = _WIN_RESERVED.sub("_", name).strip().strip(".")
    return name or "unnamed"


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:60].strip("-")


def folder_subpath(folder_name: str, delimiter: str) -> Path:
    sep = delimiter or "/"
    parts = [_safe_name(p) for p in folder_name.split(sep) if p]
    return Path(*parts) if parts else Path("INBOX")


def note_filename(date, subject: str, message_id: str) -> str:
    datestr = date.strftime("%Y-%m-%d") if date else "undated"
    slug = slugify(subject) or "no-subject"
    digest = hashlib.sha1((message_id or subject).encode("utf-8")).hexdigest()[:8]
    return f"{datestr} {slug} {digest}.md"


# --- rendering -------------------------------------------------------------

def _yaml(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render(template: str, msg, folder_name: str, attachment_names: list[str]) -> str:
    date = message_date(msg)

    if attachment_names:
        links = "\n".join(f"- `{n}`" for n in attachment_names)
        attachments_block = f"\n**Attachments:**\n{links}\n"
    else:
        attachments_block = ""

    fields = {
        "subject": _yaml(header(msg, "subject")) or "(no subject)",
        "from": _yaml(header(msg, "from")),
        "to": _yaml(header(msg, "to")),
        "cc": _yaml(header(msg, "cc")),
        "date_iso": date.isoformat() if date else "",
        "date_human": date.strftime("%a, %d %b %Y %H:%M") if date else "unknown",
        "message_id": _yaml(header(msg, "message-id")),
        "folder": _yaml(folder_name),
        "attachments_block": attachments_block,
        "body": extract_body(msg),
    }
    out = template
    for key, value in fields.items():
        out = out.replace("{{" + key + "}}", value)
    return out
