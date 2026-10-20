"""The media team's weekly triage rotation, from the media-triage repo's calendar.

mozilla/media-triage syncs its Google Calendar to `js/media.ics` every day. Each event is
one engineer's week, Saturday to Saturday, and most repeat every few weeks. Swaps are
override events (RECURRENCE-ID) and skipped weeks are EXDATEs, so the events are
expanded with recurring_ical_events, which applies both. Only the first name in SUMMARY
and the dates are kept: the file also holds attendee emails, which never leave this
module.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import date, datetime, timedelta

import icalendar
import recurring_ical_events

from .summary import EMAIL

ICS_URL = "https://raw.githubusercontent.com/mozilla/media-triage/main/js/media.ics"
_TEAM = re.compile(r"\b(media|playback)\b", re.I)
_LABEL = re.compile(r"\[[^\]]*\]|\b(?:media|playback|triage|tirage)\b", re.I)


def slot_name(summary: str) -> str | None:
    """`Chun-Min Media Triage` -> `Chun-Min`. None for an event of another team, and for a
    name that holds an email address, which must never be published."""
    if not _TEAM.search(summary):
        return None
    name = " ".join(_LABEL.sub(" ", summary).split())
    return None if not name or EMAIL.search(name) or "@" in name else name


def _day(value) -> date:
    return value.date() if isinstance(value, datetime) else value


def slots(ics_text: str, start: date, end: date) -> list[dict]:
    """Every media slot that starts in [start, end), oldest first. Two events on the same
    week, which a bad swap can leave, share the slot."""
    cal = icalendar.Calendar.from_ical(ics_text)
    weeks: dict[date, tuple[date, list[str]]] = {}
    for ev in recurring_ical_events.of(cal).between(start, end):
        name = slot_name(str(ev.get("SUMMARY", "")))
        if name is None:
            continue
        s = _day(ev["DTSTART"].dt)
        names = weeks.setdefault(s, (_day(ev["DTEND"].dt), []))[1]
        if name not in names:
            names.append(name)
    return [
        {"start": s.isoformat(), "end": e.isoformat(), "name": " / ".join(names)}
        for s, (e, names) in sorted(weeks.items())
    ]


# How many recent weeks tell who is in the rotation: more than one round.
ROUND_LOOKBACK = 20
WEEK = timedelta(days=7)


def one_round(all_slots: list[dict], today: date) -> dict:
    """One week for each engineer in the rotation, newest first, ending with the week of
    `today`; and the next slot. A week with no slot keeps its place with no name, so its
    bugs still show."""
    day = today.isoformat()
    past = [s for s in all_slots if s["start"] <= day]
    people = {n for s in past[-ROUND_LOOKBACK:] for n in s["name"].split(" / ")}
    by_start = {s["start"]: s for s in all_slots}
    current = next((s for s in past if day < s["end"]), None)
    # The rotation weeks start on Saturday.
    anchor = (
        date.fromisoformat(current["start"])
        if current
        else today - timedelta(days=(today.weekday() - 5) % 7)
    )
    weeks = []
    for k in range(len(people)):
        start = (anchor - k * WEEK).isoformat()
        slot = by_start.get(start)
        end = slot["end"] if slot else (anchor - k * WEEK + WEEK).isoformat()
        name = slot["name"] if slot else None
        weeks.append({"start": start, "end": end, "name": name, "current": k == 0})
    upcoming = [s for s in all_slots if s["start"] > day]
    return {"weeks": weeks, "next": upcoming[0] if upcoming else None}


def fetch_ics(url: str = ICS_URL) -> str:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode()
