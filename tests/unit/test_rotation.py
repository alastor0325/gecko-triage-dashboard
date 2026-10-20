from datetime import date

from triagedash import rotation

# A rotation of three people, every 3 weeks from Sat Oct 3. Bob's Oct 24 week is traded to
# Ann (an override), Cid's Oct 31 week is cancelled, and another team's event is ignored.
ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:ann
DTSTART;VALUE=DATE:20261003
DTEND;VALUE=DATE:20261010
RRULE:FREQ=WEEKLY;INTERVAL=3;BYDAY=SA
SUMMARY:Ann Media Triage
ATTENDEE;CN=ann@example.com:mailto:ann@example.com
END:VEVENT
BEGIN:VEVENT
UID:bob
DTSTART;VALUE=DATE:20261010
DTEND;VALUE=DATE:20261017
RRULE:FREQ=WEEKLY;INTERVAL=3;BYDAY=SA
SUMMARY:Bob playback triage
END:VEVENT
BEGIN:VEVENT
UID:bob
RECURRENCE-ID;VALUE=DATE:20261031
DTSTART;VALUE=DATE:20261031
DTEND;VALUE=DATE:20261107
SUMMARY:Ann Media Triage
END:VEVENT
BEGIN:VEVENT
UID:cid
DTSTART;VALUE=DATE:20261017
DTEND;VALUE=DATE:20261024
RRULE:FREQ=WEEKLY;INTERVAL=3;BYDAY=SA
EXDATE;VALUE=DATE:20261107
SUMMARY:[Incoming Triage] Cid Media Tirage
END:VEVENT
BEGIN:VEVENT
UID:gfx
DTSTART;VALUE=DATE:20261010
DTEND;VALUE=DATE:20261017
SUMMARY:Dee Graphics Triage
END:VEVENT
END:VCALENDAR
"""


def test_slot_name():
    assert rotation.slot_name("Chun-Min Media Triage") == "Chun-Min"
    assert rotation.slot_name("[Incoming Triage] Cid Media Tirage") == "Cid"
    assert rotation.slot_name("Bob playback triage") == "Bob"
    assert rotation.slot_name("Dee Graphics Triage") is None
    assert rotation.slot_name("ann@example.com Media Triage") is None


def test_slots_apply_swaps_and_cancelled_weeks_and_drop_emails():
    out = rotation.slots(ICS, date(2026, 10, 1), date(2026, 11, 15))
    assert [(s["start"], s["name"]) for s in out] == [
        ("2026-10-03", "Ann"),
        ("2026-10-10", "Bob"),
        ("2026-10-17", "Cid"),
        ("2026-10-24", "Ann"),
        ("2026-10-31", "Ann"),
        ("2026-11-14", "Ann"),
    ]
    assert out[0]["end"] == "2026-10-10"
    assert "example.com" not in str(out)


def test_one_round_ends_at_the_current_week():
    out = rotation.slots(ICS, date(2026, 10, 1), date(2026, 11, 15))
    r = rotation.one_round(out, date(2026, 10, 20))
    assert [(w["start"], w["name"], w["current"]) for w in r["weeks"]] == [
        ("2026-10-17", "Cid", True),
        ("2026-10-10", "Bob", False),
        ("2026-10-03", "Ann", False),
    ]
    assert r["next"]["start"] == "2026-10-24"
    assert rotation.one_round([], date(2026, 10, 20)) == {"weeks": [], "next": None}


def test_one_round_keeps_a_week_with_no_slot():
    out = rotation.slots(ICS, date(2026, 10, 1), date(2026, 11, 15))
    # Nov 7 is cancelled: the week is in the round with no name.
    r = rotation.one_round(out, date(2026, 11, 9))
    assert [(w["start"], w["name"]) for w in r["weeks"]] == [
        ("2026-11-07", None),
        ("2026-10-31", "Ann"),
        ("2026-10-24", "Ann"),
    ]
    assert r["weeks"][0]["end"] == "2026-11-14"
