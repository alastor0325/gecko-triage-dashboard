from datetime import UTC, datetime

from triagedash import stats

from .conftest import make_record

AS_OF = datetime(2026, 10, 14, 12, tzinfo=UTC)


def test_analyzed_that_asks_for_artifacts_needs_info():
    assert stats.category(make_record(decision="triaged", asked=["media profile"])) == "needs-info"
    assert stats.category(make_record(decision="triaged", asked=[])) == "analyzed"
    assert stats.category(make_record(decision="duplicate", asked=["log"])) == "close"
    v = stats.run_view(make_record(decision="triaged", asked=["media profile"]))
    assert v["decision"] == "analyzed, still asks for artifacts"
    assert stats.run_view(make_record(decision="triaged"))["decision"] == "analyzed"


def test_old_and_new_name_of_analyzed():
    assert (
        stats.category(make_record(decision="triaged"))
        == stats.category(make_record(decision="analyzed"))
        == "analyzed"
    )
    assert stats.run_view(make_record(decision="analyzed"))["decision"] == "analyzed"
    assert stats.acted(make_record(decision="analyzed"))
    assert not stats.acted(make_record(decision="brand_new"))
    assert not stats.acted(make_record(decision="needs_info", outcome="skipped"))
    assert not stats.acted(make_record(decision="watching", comment=None))
    assert stats.acted(make_record(decision="watching", comment=None, severity="S3"))


def test_category():
    assert stats.category(make_record(decision="triaged")) == "analyzed"
    assert stats.category(make_record(decision="needs_info")) == "needs-info"
    for d in ("duplicate", "invalid", "wrong_component", "incomplete"):
        assert stats.category(make_record(decision=d)) == "close"
    assert stats.category(make_record(decision="watching")) == "needs-info"
    assert stats.category(make_record(decision="stalled")) == "needs-info"


def test_labels():
    assert stats.resolution_label("INCOMPLETE") == "Incomplete"
    assert stats.resolution_label(None) is None
    assert stats.move_label("Core :: Web Audio") == "Web Audio"
    assert stats.move_label("Toolkit :: Media") == "Toolkit :: Media"
    v = stats.run_view(make_record(resolution="DUPLICATE", move_to="Core :: Web Audio"))
    assert (v["resolution"], v["move_to"]) == ("Duplicate", "Web Audio")


def test_close_kind():
    assert stats.close_kind(make_record(resolution="DUPLICATE")) == "Duplicate"
    assert stats.close_kind(make_record(move_to="Core :: Web Audio")) == "Reassigned to Web Audio"
    assert (
        stats.close_kind(make_record(move_to="Toolkit :: Media"))
        == "Reassigned to Toolkit :: Media"
    )
    assert stats.close_kind(make_record()) is None


def test_tags():
    assert stats.tags(make_record(keywords_add=["regression"])) == ["regression"]
    assert stats.tags(make_record(regressed_by_add=[5])) == ["regression"]
    reporter, dev = {"role": "reporter", "name": None}, {"role": "other", "name": "Dev (:dev)"}
    assert stats.tags(make_record(needinfo=[reporter, dev])) == ["dev needinfo"]
    assert stats.tags(make_record(needinfo=[reporter])) == []


def test_is_new():
    assert stats.is_new("2026-10-08T00:00:00Z", AS_OF)
    assert not stats.is_new("2026-10-01T00:00:00Z", AS_OF)
    assert not stats.is_new(None, AS_OF)


def test_acted():
    assert stats.acted(make_record())
    assert not stats.acted(make_record(error=True))
    assert not stats.acted(make_record(decision="skipped"))
    assert not stats.acted(make_record(decision=None))
    assert not stats.acted(make_record(started_at=None))


def test_team_page_counts_posted_runs():
    page = stats.team_page([make_record(posted=True), make_record(2)], AS_OF)
    assert page["posted"] == 1


def test_outcome_tags():
    assert stats.tags(make_record(posted=True, outcome="posted")) == []
    assert stats.tags(make_record(outcome="awaiting review")) == []
    assert stats.tags(make_record(posted=True, outcome="partly posted")) == ["partly posted"]
    assert stats.tags(make_record(outcome="apply failed")) == ["apply failed"]
    assert stats.tags(make_record(outcome="rejected", rejected=True)) == ["rejected"]
    assert stats.tags(make_record(outcome="posted", posted=True, rejected=True)) == ["rejected"]


def test_warning():
    assert stats.warning(make_record(rejected=True, pending_actions=2)) == "do not apply"
    assert stats.warning(make_record(rejected=True, posted=True)) == "rejected but posted"
    assert stats.warning(make_record(rejected=True, pending_actions=0)) is None
    assert stats.warning(make_record()) is None


def test_team_page_counts_bugs_awaiting_review():
    page = stats.team_page(
        [make_record(outcome="awaiting review", source="hackbot"), make_record(2)], AS_OF
    )
    assert page["awaiting"] == 1


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
    assert one["filed"] == "2026-01-01T00:00:00Z"
    assert one["first_run"] == "2026-10-06T10:00:00+00:00"


def test_shown_runs_keep_daily_history_even_unposted():
    days = [
        make_record(started_at=f"2026-10-1{d}T00:00:00+00:00", source="daily") for d in (7, 6, 5)
    ]
    test = make_record(started_at="2026-10-14T00:00:00+00:00")
    assert stats.shown_runs(days) == days
    assert stats.shown_runs([days[0], test, days[1]]) == [days[0], days[1]]


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
    assert o["1w"]["close_kinds"] == {"Duplicate": 1, "Reassigned to Widget: Gtk": 1}
    assert o["1w"]["severity"] == {"S1": 0, "S2": 0, "S3": 1, "S4": 0}


def test_team_page():
    page = stats.team_page([make_record()], AS_OF)
    assert page["as_of"] == "2026-10-14T12:00:00+00:00"
    assert page["posted"] == 0
    assert [c["key"] for c in page["categories"]] == ["analyzed", "needs-info", "close"]
    assert page["categories"][2] == {
        "key": "close",
        "label": "Close / Reassign",
        "color": "#FF0039",
    }
    assert "risk" not in page
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


def test_ran_at_has_passes_and_official_runs_only():
    passes = [{"team": "media", "at": "2026-10-13T05:00:00+00:00", "selected": 0}]
    records = [
        make_record(1, source="daily", started_at="2026-10-12T05:00:00+00:00"),
        make_record(2, source="test", posted=True, started_at="2026-10-11T05:00:00+00:00"),
        make_record(3, source="daily", started_at="2026-09-01T05:00:00+00:00"),
    ]
    ran = stats.ran_at(records, passes, "2026-10-01T00:00:00+00:00")
    assert ran == ["2026-10-12T05:00:00+00:00", "2026-10-13T05:00:00+00:00"]


def test_known_until_is_the_clock_or_the_first_hackbot_run():
    assert stats.known_until([make_record(source="daily")], AS_OF) == AS_OF.isoformat()
    records = [
        make_record(1, source="hackbot", started_at="2026-10-13T05:00:00+00:00"),
        make_record(2, source="hackbot", started_at="2026-10-12T05:00:00+00:00"),
    ]
    assert stats.known_until(records, AS_OF) == "2026-10-12T05:00:00+00:00"


def test_team_page_day_marks_data():
    passes = [{"team": "media", "at": "2026-10-13T05:00:00+00:00", "selected": 0}]
    page = stats.team_page([make_record(source="daily")], AS_OF, passes)
    assert page["ran_at"] == ["2026-10-13T05:00:00+00:00", "2026-10-14T10:00:00+00:00"]
    assert page["known_until"] == AS_OF.isoformat()
    assert page["first_run"] == "2026-10-13T05:00:00+00:00"
    test_page = stats.team_page([make_record()], AS_OF)
    assert test_page["ran_at"] == []
    assert test_page["first_run"] == "2026-10-14T10:00:00+00:00"


def test_overview_counts_issue_types():
    runs = [
        make_record(1, issue_type="performance"),
        make_record(2, issue_type="performance"),
        make_record(3, issue_type="other"),
        make_record(4),
    ]
    o = stats.overview(runs, AS_OF)["1w"]
    assert o["issue_types"] == {"performance": 2, "other": 1, "unknown": 1}
    assert "other_notes" not in o
    assert stats.run_view(runs[3])["issue_type"] == "unknown"


def test_close_action_follows_close_kind_order():
    dup = make_record(decision="duplicate", resolution="DUPLICATE", move_to="Core :: Widget: Gtk")
    moved = make_record(decision="wrong_component", move_to="Core :: Widget: Gtk")
    assert (stats.close_action(dup), stats.close_action(moved)) == ("Closed", "Reassigned")
    assert stats.run_view(dup)["close_action"] == "Closed"
    assert stats.run_view(make_record(decision="triaged"))["close_action"] is None
    assert stats.run_view(dup)["label_kind"] == "closed"
    assert stats.run_view(moved)["label_kind"] == "reassigned"
    assert stats.run_view(make_record(decision="incomplete"))["label_kind"] == "close"
    assert stats.run_view(make_record(decision="needs_info"))["label_kind"] == "needs-info"
