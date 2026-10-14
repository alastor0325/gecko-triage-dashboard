from datetime import datetime

from triagedash import stats

from .conftest import make_record, make_ref

AS_OF = datetime(2026, 10, 14, 12)


def test_latest_runs_prefers_newest_ok_run():
    old = make_record(started_at="2026-10-13T10:00:00", round_="r1")
    new = make_record(started_at="2026-10-14T10:00:00", round_="r2")
    failed = make_record(started_at="2026-10-14T11:00:00", round_="r3", error=True)
    assert [r["round"] for r in stats.latest_runs([new, failed, old])] == ["r2"]


def test_latest_runs_keeps_failed_bug_and_sorts_newest_first():
    failed = make_record(1, error=True, started_at="2026-10-12T00:00:00")
    other = make_record(2)
    assert stats.latest_runs([failed, other]) == [other, failed]


def test_in_window():
    recent = make_record(started_at="2026-10-13T00:00:00")
    old = make_record(started_at="2026-09-01T00:00:00")
    assert stats.in_window([recent, old], AS_OF, 7) == [recent]
    assert stats.in_window([recent, old], AS_OF, None) == [recent, old]


def test_overview_counts():
    bugs = [
        make_record(1, severity="S3", priority="P3"),
        make_record(2, decision="needs_info", needinfo=["reporter"]),
        make_record(3, decision="duplicate", resolution="DUPLICATE"),
        make_record(4, decision="wrong_component", move_to="Core :: Web Audio"),
        make_record(5, decision="skipped"),
    ]
    o = stats.overview(bugs, bugs)
    assert o["tiles"] == {"triaged": 4, "sp_set": 1, "needinfo": 1, "closed": 1, "moved": 1}
    assert o["decisions"]["skipped"] == 1
    assert o["severity"] == {"S3": 1}
    assert o["needinfo_roles"] == {"reporter": 1}
    assert o["weekly"] == {"2026-W42": 4}


def test_waiting():
    asked = make_record(needinfo=["reporter"], started_at="2026-10-12T12:00:00")
    rows = stats.waiting([asked, make_record(2)], AS_OF)
    assert rows == [{"run_id": asked["run_id"], "days": 2}]


def test_health_by_round():
    runs = [
        make_record(1, round_="r1", cost_usd=1.0, unread=["profile"]),
        make_record(2, round_="r1", error=True, cost_usd=None),
        make_record(3, round_="r2", cost_usd=3.0),
    ]
    h = stats.health(runs)
    assert (h["runs"], h["errors"], h["cost_total"], h["cost_median"]) == (3, 1, 4.0, 2.0)
    assert h["unread"] == {"profile": 1}
    assert h["rounds"]["r1"] == {"commit": "abc", "runs": 2, "errors": 1, "cost_usd": 1.0}


def test_agreement():
    baseline = {
        1: make_ref("analyzed", severity="S3", priority="P3"),
        2: make_ref("needs-info", needinfo_count=1),
    }
    first = make_record(1, severity="S3", priority="P2", round_="r1")
    wrong = make_record(2, decision="triaged", round_="r1", started_at="2026-10-13T10:00:00")
    fixed = make_record(2, decision="needs_info", needinfo=["reporter"], round_="r2")
    a = stats.agreement([first, wrong, fixed, make_record(3)], baseline)
    by_run = {b["run_id"]: b for b in a["bugs"]}
    assert set(by_run) == {first["run_id"], fixed["run_id"]}
    assert by_run[first["run_id"]]["diffs"] == ["priority: P2 vs P3"]
    assert all(b["same"] for b in a["bugs"])
    assert a["rounds"] == {"r1": {"runs": 2, "same": 1}, "r2": {"runs": 1, "same": 1}}


def test_team_page_stores_each_shown_run_once():
    old = make_record(1, started_at="2026-08-01T00:00:00", run_id="old")
    new = make_record(2, run_id="new")
    page = stats.team_page([old, new], {}, AS_OF)
    assert list(page["periods"]) == list(stats.PERIODS)
    assert page["periods"]["1w"]["bugs"] == ["new"]
    assert page["periods"]["all"]["bugs"] == ["new", "old"]
    assert page["periods"]["all"]["label"] == "All"
    assert set(page["runs"]) == {"old", "new"}
    assert page["posted"] is False
