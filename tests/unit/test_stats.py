from datetime import UTC, datetime

from triagedash import stats

from .conftest import make_record


def test_categories_in_risk_order():
    r = make_record(
        resolution="DUPLICATE", move_to="Core :: Web Audio", severity="S3", needinfo=["reporter"]
    )
    assert stats.categories(r) == ["closed", "moved", "sp", "needinfo"]
    assert stats.categories(make_record(priority="P3")) == ["sp"]
    assert stats.categories(make_record()) == []


def test_tags():
    assert stats.tags(make_record(keywords_add=["regression"])) == ["regression"]
    assert stats.tags(make_record(regressed_by_add=[5])) == ["regression"]
    assert stats.tags(make_record(needinfo=["reporter", "other"])) == ["dev needinfo"]
    assert stats.tags(make_record(needinfo=["reporter"])) == []


def test_acted():
    assert stats.acted(make_record())
    assert not stats.acted(make_record(error=True))
    assert not stats.acted(make_record(decision="skipped"))
    assert not stats.acted(make_record(started_at=None))


def test_run_view_keeps_only_page_fields():
    v = stats.run_view(make_record(severity="S3", round="r9a"))
    assert (v["categories"], v["round"]) == (["sp"], "r9a")
    assert not {"run_id", "error", "team", "decision", "bug_id", "title"} & set(v)
    assert v["posted"] is False


def test_bugs_group_runs_newest_first_and_drop_no_change_runs():
    runs = [
        make_record(1, started_at="2026-10-06T10:00:00", run_id="a", round="r1"),
        make_record(1, started_at="2026-10-13T10:00:00", run_id="b", round="r2", title="new title"),
        make_record(1, started_at="2026-10-14T10:00:00", run_id="c", error=True),
        make_record(2, started_at="2026-10-14T12:00:00", decision="skipped"),
    ]
    (b,) = stats.bugs(runs, datetime(2026, 10, 14, 12, tzinfo=UTC))
    assert b["bug_id"] == 1
    assert b["title"] == "new title"
    assert [r["round"] for r in b["runs"]] == ["r2", "r1"]


def test_rounds_newest_first():
    runs = [
        make_record(1, started_at="2026-10-06T10:00:00", round="r1"),
        make_record(2, started_at="2026-10-13T10:00:00", round="r2"),
        make_record(3, started_at="2026-10-05T10:00:00", round="r1"),
        make_record(4, started_at="2026-10-14T10:00:00", round="r3", error=True),
    ]
    assert stats.rounds(runs) == ["r2", "r1"]
    assert stats.rounds([make_record(round=None)]) == []


def test_recent_counts():
    runs = [
        make_record(1, started_at="2026-10-13T10:00:00", resolution="DUPLICATE"),
        make_record(2, started_at="2026-10-14T10:00:00", severity="S3"),
        make_record(3, started_at="2026-09-01T10:00:00", move_to="Core :: Web Audio"),
    ]
    page = stats.team_page(runs, datetime(2026, 10, 14, 12, tzinfo=UTC))
    assert stats.recent_counts(page) == {"bugs": 2, "closed_or_moved": 1}


def test_team_page():
    page = stats.team_page([make_record()], datetime(2026, 10, 14, 12, tzinfo=UTC))
    assert page["as_of"] == "2026-10-14T12:00:00+00:00"
    assert page["windows"] == {
        "7d": "2026-10-07T12:00:00+00:00",
        "30d": "2026-09-14T12:00:00+00:00",
    }
    assert page["posted"] is False
    assert page["categories"] == list(stats.CATEGORIES)
    assert [b["bug_id"] for b in page["bugs"]] == [100]
    assert stats.team_page([], datetime(2026, 10, 14, tzinfo=UTC))["bugs"] == []


def test_is_new():
    as_of = datetime(2026, 10, 14, 12, tzinfo=UTC)
    assert stats.is_new("2026-10-08T00:00:00Z", as_of)
    assert not stats.is_new("2026-10-01T00:00:00Z", as_of)
    assert not stats.is_new(None, as_of)


def test_bug_tags_new():
    as_of = datetime(2026, 10, 14, 12, tzinfo=UTC)
    (fresh,) = stats.bugs([make_record(filed="2026-10-13T00:00:00Z")], as_of)
    (old,) = stats.bugs([make_record(filed="2026-01-01T00:00:00Z")], as_of)
    assert (fresh["tags"], old["tags"]) == (["new"], [])
