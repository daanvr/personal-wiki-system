"""Thin compatibility layer over the third-party ``caldav`` package."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator


def _require_caldav():
    try:
        import caldav  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Missing calendar dependencies. From modules/calendar, run: "
            "python3 -m pip install -r requirements.txt"
        ) from exc
    return caldav


@contextmanager
def connect(url: str, username: str, password: str) -> Iterator[object]:
    caldav = _require_caldav()

    if hasattr(caldav, "DAVClient"):
        try:
            client = caldav.DAVClient(url=url, username=username, password=password)
        except TypeError:
            client = caldav.DAVClient(url, username=username, password=password)
    else:
        client = caldav.get_davclient(url=url, username=username, password=password)

    try:
        yield client
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def list_calendars(client) -> list[object]:
    principal = client.principal()
    for method_name in ("get_calendars", "calendars"):
        method = getattr(principal, method_name, None)
        if callable(method):
            return list(method())
    raise RuntimeError("The caldav client did not expose a calendar listing method.")


def calendar_name(calendar) -> str:
    for attr in ("name", "display_name"):
        value = getattr(calendar, attr, None)
        if value:
            return str(value)
    method = getattr(calendar, "get_display_name", None)
    if callable(method):
        try:
            value = method()
            if value:
                return str(value)
        except Exception:
            pass
    return str(calendar_url(calendar)).rstrip("/").rsplit("/", 1)[-1] or "calendar"


def calendar_url(calendar) -> str:
    value = getattr(calendar, "url", None)
    if value:
        return str(value)
    return str(calendar)


def search_events(calendar, start: datetime, end: datetime, expand: bool = False) -> list[object]:
    method = getattr(calendar, "date_search", None)
    if callable(method):
        attempts = (
            lambda: method(start=start, end=end, expand=expand),
            lambda: method(start, end, expand=expand),
            lambda: method(start=start, end=end),
            lambda: method(start, end),
        )
        for attempt in attempts:
            try:
                return list(attempt())
            except TypeError:
                continue
    method = getattr(calendar, "search", None)
    if callable(method):
        return list(method(start=start, end=end, event=True, expand=expand))
    raise RuntimeError(f"Calendar {calendar_name(calendar)} does not support date search.")


def resource_data(resource) -> str:
    data = getattr(resource, "data", None)
    if data is None:
        load = getattr(resource, "load", None)
        if callable(load):
            load()
            data = getattr(resource, "data", None)
    if callable(data):
        data = data()
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    if isinstance(data, str):
        return data

    instance = getattr(resource, "icalendar_instance", None)
    if instance is not None:
        raw = instance.to_ical()
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    raise RuntimeError("Could not read iCalendar data from CalDAV resource.")


def resource_url(resource) -> str:
    value = getattr(resource, "url", None)
    return str(value) if value else ""


def resource_etag(resource) -> str:
    value = getattr(resource, "etag", None)
    if value:
        return str(value)
    method = getattr(resource, "get_etag", None)
    if callable(method):
        try:
            return str(method() or "")
        except Exception:
            return ""
    return ""
