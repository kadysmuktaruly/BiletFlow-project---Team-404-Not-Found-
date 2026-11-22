"""Calendar export (.ics, RFC 5545) for an event page (SRS 4.2: "calendar exports keep the
correct local time").

The start and end are written in the event's own IANA zone (`DTSTART;TZID=Asia/Almaty:...`)
with a matching VTIMEZONE, so a calendar shows the local time the organizer set, wherever
the reader is. A VTIMEZONE we write ourselves can only describe a fixed offset, so for a
zone with daylight saving around the event the times are written in UTC instead, which every
calendar converts correctly.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.enums import EventStatus
from app.models import Event

_PRODID = "-//BiletFlow//Event calendar//EN"
_MAX_DESCRIPTION = 1000


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """RFC 5545 3.1: lines longer than 75 octets continue on the next line after a space,
    never splitting a UTF-8 character."""
    out: list[str] = []
    current = ""
    limit = 75
    for char in line:
        if len((current + char).encode()) > limit:
            out.append(current)
            current = " " + char
            limit = 75
        else:
            current += char
    out.append(current)
    return "\r\n".join(out)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _offset(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, mins = divmod(abs(minutes), 60)
    return f"{sign}{hours:02d}{mins:02d}"


def _fixed_offset(zone: ZoneInfo, event: Event) -> timedelta | None:
    """The zone's UTC offset if it doesn't change within half a year of the event."""
    probes = [event.starts_at + timedelta(days=d) for d in range(-183, 184, 30)]
    offsets = {p.astimezone(zone).utcoffset() for p in [*probes, event.ends_at]}
    if len(offsets) != 1:
        return None
    (offset,) = offsets
    return offset


def event_ics(event: Event, page_url: str, now: datetime | None = None) -> str:
    zone = ZoneInfo(event.timezone)
    offset = _fixed_offset(zone, event)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    if offset is not None:
        name = event.starts_at.astimezone(zone).tzname() or _offset(offset)
        lines += [
            "BEGIN:VTIMEZONE",
            f"TZID:{event.timezone}",
            "BEGIN:STANDARD",
            "DTSTART:19700101T000000",
            f"TZOFFSETFROM:{_offset(offset)}",
            f"TZOFFSETTO:{_offset(offset)}",
            f"TZNAME:{_escape(name)}",
            "END:STANDARD",
            "END:VTIMEZONE",
        ]

    def when(prop: str, value: datetime) -> str:
        if offset is None:
            return f"{prop}:{_utc(value)}"
        local = value.astimezone(zone).strftime("%Y%m%dT%H%M%S")
        return f"{prop};TZID={event.timezone}:{local}"

    description = (event.description or "").strip()
    if len(description) > _MAX_DESCRIPTION:
        description = description[: _MAX_DESCRIPTION - 1].rstrip() + "…"
    description = f"{description}\n\n{page_url}".strip()

    lines += [
        "BEGIN:VEVENT",
        f"UID:{event.id}@biletflow",
        f"DTSTAMP:{_utc(now or datetime.now(UTC))}",
        when("DTSTART", event.starts_at),
        when("DTEND", event.ends_at),
        f"SUMMARY:{_escape(event.title)}",
        f"DESCRIPTION:{_escape(description)}",
        f"URL:{page_url}",
        f"STATUS:{'CANCELLED' if event.status is EventStatus.CANCELLED else 'CONFIRMED'}",
    ]
    if event.venue is not None:
        venue = event.venue
        parts = [venue.name, venue.address_line1, venue.address_line2, venue.city]
        lines.append(f"LOCATION:{_escape(', '.join(p for p in parts if p))}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
