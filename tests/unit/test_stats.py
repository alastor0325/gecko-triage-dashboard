from datetime import UTC, datetime

from triagedash import stats

from .conftest import make_record

AS_OF = datetime(2026, 10, 14, 12, tzinfo=UTC)


def test_category():
    assert stats.category(make_record(decision="triaged")) == "analyzed"
    assert stats.category(make_record(decision="needs_info")) == "needs-info"
    for d in ("duplicate", "invalid", "wrong_component", "incomplete", "stalled"):
        assert stats.category(make_record(decision=d)) == "close"
    assert stats.category(make_record(decision="watching")) is None


def test_labels():
    assert stats.resolution_label("INCOMPLETE") == "Incomplete"
    assert stats.resolution_label(None) is None
    assert stats.move_label("Core :: Web Audio") == "Web Audio"
    assert stats.move_label("Toolkit :: Media") == "Toolkit :: Media"
    v = stats.run_view(make_record(resolution="DUPLICATE", move_to="Core :: Web Audio"))
    assert (v["resolution"], v["move_to"]) == ("Duplicate", "Web Audio")


def test_close_kind():
    assert stats.close_kind(make_record(resolution="DUPLICATE")) == "Duplicate"
    assert stats.close_kind(make_record(move_to="Core :: Web Audio")) == "Moved to Web Audio"
    assert stats.close_kind(make_record(move_to="Toolkit :: Media")) == "Moved to Toolkit :: Media"
    assert stats.close_kind(make_record()) is None


def test_tags():
    assert stats.tags(make_record(keywords_add=["regression"])) == ["regression"]
    assert stats.tags(make_record(regressed_by_add=[5])) == ["regression"]
    assert stats.tags(make_record(needinfo=["reporter", "other"])) == ["dev needinfo"]
    assert stats.tags(make_record(needinfo=["reporter"])) == []


def test_is_new():
    assert stats.is_new("2026-10-08T00:00:00Z", AS_OF)
    assert not stats.is_new("2026-10-01T00:00:00Z", AS_OF)
    assert not stats.is_new(None, AS_OF)


def test_acted():
    assert stats.acted(make_record())
    assert not stats.acted(make_record(error=True))
    assert not stats.acted(make_record(decision="skipped"))
    assert not stats.acted(make_record(started_at=None))


def test_decision_label():
    assert stats.decision_label("triaged") == "analyzed"
    assert stats.decision_label("wrong_component") == "wrong component"
    assert stats.decision_label(None) == ""


def test_run_view_keeps_only_page_fields():
    v = stats.run_view(make_record(decision="wrong_component", comment="**Moved**"))
    assert (v["category"], v["decision"]) == ("close", "wrong component")
    assert v["comment_html"] == "<p><strong>Moved</strong></p>"
    assert stats.run_view(make_record(comment=None))["comment_html"] is None
    assert not {"run_id", "error", "team", "bug_id", "title", "comment"} & set(v)


def test_in_period():
    recent = make_record(started_at="2026-10-13T00:00:00+00:00")
    old = make_record(started_at="2026-09-01T00:00:00+00:00")
    failed = make_record(started_at="2026-10-13T00:00:00+00:00", error=True)
    assert stats.in_period([recent, old, failed], AS_OF, "1w") == [recent]
    assert stats.in_period([recent, old, failed], AS_OF, "3m") == [recent, old]


def test_bugs_newest_first():
    runs = [
        make_record(1, started_at="2026-10-06T10:00:00+00:00", run_id="a"),
        make_record(
            1,
            started_at="2026-10-13T10:00:00+00:00",
            run_id="b",
            title="new title",
            filed="2026-01-01T00:00:00Z",
        ),
        make_record(2, started_at="2026-10-14T10:00:00+00:00", decision="skipped"),
        make_record(3, filed="2026-10-13T00:00:00Z"),
    ]
    one, three = sorted(stats.bugs(runs, AS_OF), key=lambda b: b["bug_id"])
    assert one["title"] == "new title"
    assert [r["started_at"][:10] for r in one["runs"]] == ["2026-10-13"]
    assert (one["tags"], three["tags"]) == ([], ["new"])


def test_shown_runs_drop_dry_run_history():
    posted = [make_record(started_at=f"2026-10-1{d}T00:00:00+00:00", posted=True) for d in (4, 3)]
    dry = [make_record(started_at=f"2026-10-1{d}T00:00:00+00:00") for d in (4, 3)]
    assert stats.shown_runs(posted) == posted
    assert stats.shown_runs(dry) == dry[:1]
    assert stats.shown_runs([posted[0], dry[1]]) == [posted[0]]
    assert stats.shown_runs([dry[0], posted[1]]) == [dry[0]]


def test_overview():
    runs = [
        make_record(1, decision="triaged", severity="S3"),
        make_record(2, decision="duplicate", resolution="DUPLICATE"),
        make_record(3, decision="wrong_component", move_to="Core :: Widget: Gtk"),
        make_record(4, decision="needs_info", started_at="2026-09-20T10:00:00+00:00"),
    ]
    o = stats.overview(runs, AS_OF)
    assert o["1w"]["counts"] == {"all": 3, "analyzed": 1, "needs-info": 0, "close": 2}
    assert o["1m"]["counts"]["needs-info"] == 1
    assert o["1w"]["close_kinds"] == {"Duplicate": 1, "Moved to Widget: Gtk": 1}
    assert o["1w"]["severity"] == {"S1": 0, "S2": 0, "S3": 1, "S4": 0}


def test_team_page():
    page = stats.team_page([make_record()], AS_OF)
    assert page["as_of"] == "2026-10-14T12:00:00+00:00"
    assert page["posted"] is False
    assert [c["key"] for c in page["categories"]] == ["analyzed", "needs-info", "close"]
    assert page["categories"][2] == {
        "key": "close",
        "label": "Close / Reassign",
        "color": "#FF0039",
        "harm": True,
    }
    assert page["risk"][0] == "close"
    assert page["periods"][0] == {
        "key": "1w",
        "label": "1-Week",
        "days": 7,
        "start": "2026-10-07T12:00:00+00:00",
    }
    assert [b["bug_id"] for b in page["bugs"]] == [100]


def test_team_page_keeps_only_the_longest_period():
    old = make_record(1, started_at="2026-06-01T00:00:00+00:00")
    page = stats.team_page([old, make_record(2)], AS_OF)
    assert [b["bug_id"] for b in page["bugs"]] == [2]
