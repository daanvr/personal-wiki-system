"""Parse iCalendar VEVENTs and render them as Markdown notes."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timezone
from pathlib import Path

_WIN_RESERVED = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _require_icalendar():
    try:
        import icalendar  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Missing calendar dependencies. From modules/calendar, run: "
            "python3 -m pip install -r requirements.txt"
        ) from exc
    return icalendar


def parse_events(raw: str) -> list[object]:
    icalendar = _require_icalendar()
    calendar = icalendar.Calendar.from_ical(raw)
    return [component for component in calendar.walk() if component.name == "VEVENT"]


def _safe_name(name: str) -> str:
    name = _WIN_RESERVED.sub("_", name).strip().strip(".")
    return name or "unnamed"


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:60].strip("-")


def calendar_subpath(name: str) -> Path:
    return Path(_safe_name(name))


def prop(component, name: str) -> str:
    value = component.get(name)
    return str(value).strip() if value is not None else ""


def decoded(component, name: str):
    try:
        return component.decoded(name)
    except KeyError:
        return None


def _as_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    return None


def _iso(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def event_key(calendar_url: str, component) -> str:
    uid = prop(component, "uid")
    recurrence_id = prop(component, "recurrence-id")
    raw = f"{calendar_url}|{uid}|{recurrence_id}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def note_filename(calendar_url: str, component) -> str:
    start = _as_datetime(decoded(component, "dtstart"))
    datestr = start.strftime("%Y-%m-%d") if start else "undated"
    summary = prop(component, "summary") or "no-title"
    digest = event_key(calendar_url, component)[:8]
    return f"{datestr} {slugify(summary) or 'no-title'} {digest}.md"


def _yaml(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _attendees(component) -> list[str]:
    value = component.get("attendee")
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def render(template: str, component, calendar_name: str, calendar_url: str, resource_url: str) -> str:
    start = decoded(component, "dtstart")
    end = decoded(component, "dtend")
    attendees = _attendees(component)
    attendees_block = "\n".join(f"- {a}" for a in attendees) if attendees else ""

    fields = {
        "title": _yaml(prop(component, "summary") or "(no title)"),
        "calendar": _yaml(calendar_name),
        "calendar_url": _yaml(calendar_url),
        "resource_url": _yaml(resource_url),
        "uid": _yaml(prop(component, "uid")),
        "status": _yaml(prop(component, "status")),
        "start_iso": _iso(start),
        "end_iso": _iso(end),
        "location": _yaml(prop(component, "location")),
        "organizer": _yaml(prop(component, "organizer")),
        "attendees_block": attendees_block,
        "description": prop(component, "description"),
    }
    out = template
    for key, value in fields.items():
        out = out.replace("{{" + key + "}}", value)
    return out
