"""Parse iCalendar VEVENTs and render them as Markdown notes."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from _shared import wikilib


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


def calendar_subpath(name: str) -> Path:
    return Path(wikilib.safe_name(name))


def prop(component, name: str) -> str:
    value = component.get(name)
    return str(value).strip() if value is not None else ""


def decoded(component, name: str):
    try:
        return component.decoded(name)
    except (KeyError, ValueError, TypeError):
        # Missing property, or a value icalendar cannot decode. Depending on
        # the icalendar version a malformed date either drops the property
        # (KeyError) or raises — treat both as "no usable value".
        return None


def _is_all_day(value) -> bool:
    """True for a date-only (VALUE=DATE) property value."""
    return isinstance(value, date) and not isinstance(value, datetime)


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
    # Only real date/datetime values render; icalendar 7.x hands back raw
    # strings for malformed dates, which must not leak into frontmatter.
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return ""


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
    return f"{datestr} {wikilib.slugify(summary) or 'no-title'} {digest}.md"


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
    all_day = _is_all_day(start)
    if _is_all_day(end):
        # RFC 5545: an all-day DTEND is exclusive (the day after the last
        # day) — render the inclusive last day instead.
        end = end - timedelta(days=1)
    attendees = _attendees(component)
    attendees_block = "\n".join(f"- {a}" for a in attendees) if attendees else ""

    fields = {
        "title": wikilib.yaml_escape(prop(component, "summary") or "(no title)"),
        "calendar": wikilib.yaml_escape(calendar_name),
        "calendar_url": wikilib.yaml_escape(calendar_url),
        "resource_url": wikilib.yaml_escape(resource_url),
        "uid": wikilib.yaml_escape(prop(component, "uid")),
        "status": wikilib.yaml_escape(prop(component, "status")),
        "start_iso": _iso(start),
        "end_iso": _iso(end),
        "all_day": "true" if all_day else "false",
        "location": wikilib.yaml_escape(prop(component, "location")),
        "organizer": wikilib.yaml_escape(prop(component, "organizer")),
        "attendees_block": attendees_block,
        "description": prop(component, "description"),
    }
    return wikilib.render_template(template, fields)
