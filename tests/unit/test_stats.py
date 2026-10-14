from datetime import date, datetime

from triagedash import stats

from .conftest import make_record


def test_categories_in_risk_order():
    r = make_record(
        resolution="DUPLICATE", move_to="Core :: Web Audio", severity="S3", needinfo=["reporter"]
    )
    assert stats.categories(r) == ["closed", "moved", "sp", "needinfo"]
    assert stats.categories(make_record(priority="P3")) == ["sp"]
    assert stats.categories(make_record()) == []


def test_acted():
    assert stats.acted(make_record())
    assert not stats.acted(make_record(error=True))
    assert not stats.acted(make_record(decision="skipped"))
    assert not stats.acted(make_record(started_at=None))


def test_week_of():
    assert stats.week_of("2026-10-14T17:40:25") == ("2026-W42", date(2026, 10, 12))
    assert stats.week_of("2026-10-18T23:00:00") == ("2026-W42", date(2026, 10, 12))
    assert stats.week_of("2026-10-19T00:00:00") == ("2026-W43", date(2026, 10, 19))


def test_latest_runs():
    old = make_record(1, started_at="2026-10-13T10:00:00", run_id="old")
    new = make_record(1, started_at="2026-10-14T10:00:00", run_id="new")
    other = make_record(2, started_at="2026-10-12T10:00:00", run_id="other")
    assert {r["run_id"] for r in stats.latest_runs([new, other, old])} == {"new", "other"}


def test_row_keeps_no_run_details():
    r = stats.row(make_record(severity="S3"))
    assert r["categories"] == ["sp"]
    assert not {"run_id", "error", "team", "decision"} & set(r)


def test_weeks_groups_newest_first_and_counts():
    runs = [
        make_record(1, started_at="2026-10-06T10:00:00", resolution="DUPLICATE"),
        make_record(2, started_at="2026-10-13T10:00:00", severity="S3", needinfo=["reporter"]),
        make_record(3, started_at="2026-10-14T10:00:00", move_to="Core :: Web Audio"),
        make_record(4, started_at="2026-10-14T11:00:00", error=True),
        make_record(5, started_at="2026-10-14T12:00:00", decision="skipped"),
    ]
    w42, w41 = stats.weeks(runs)
    assert (w42["key"], w42["start"], w42["end"]) == ("2026-W42", "2026-10-12", "2026-10-18")
    assert [r["bug_id"] for r in w42["rows"]] == [3, 2]  # moved before S/P
    assert w42["counts"] == {"all": 2, "closed": 0, "moved": 1, "sp": 1, "needinfo": 1}
    assert w41["counts"]["closed"] == 1


def test_bug_in_two_weeks_shows_in_both():
    runs = [
        make_record(1, started_at="2026-10-06T10:00:00"),
        make_record(1, started_at="2026-10-13T10:00:00"),
    ]
    assert [len(w["rows"]) for w in stats.weeks(runs)] == [1, 1]


def test_team_page():
    page = stats.team_page([make_record()], datetime(2026, 10, 14, 12))
    assert page["as_of"] == "2026-10-14T12:00:00"
    assert page["posted"] is False
    assert [w["key"] for w in page["weeks"]] == ["2026-W42"]
    assert page["categories"] == list(stats.CATEGORIES)
    assert stats.team_page([], datetime(2026, 10, 14))["weeks"] == []


def test_by_risk_then_newest():
    rows = [
        stats.row(make_record(1, started_at="2026-10-14T09:00:00")),
        stats.row(make_record(2, started_at="2026-10-13T09:00:00", needinfo=["reporter"])),
        stats.row(make_record(3, started_at="2026-10-14T09:00:00", needinfo=["reporter"])),
        stats.row(make_record(4, started_at="2026-10-12T09:00:00", resolution="INVALID")),
    ]
    assert [r["bug_id"] for r in stats.by_risk(rows)] == [4, 3, 2, 1]


def test_week_of_aware_utc():
    assert stats.week_of("2026-10-18T23:30:00+00:00")[0] == "2026-W42"
