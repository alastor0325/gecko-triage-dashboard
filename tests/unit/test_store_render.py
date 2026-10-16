from datetime import UTC, datetime

from triagedash import render, stats, store
from triagedash.store import apply_log
from triagedash.teams import TEAMS, is_shown

from .conftest import make_record


def test_merge_records_upserts_by_run_id():
    a = make_record(1, run_id="x", decision="triaged")
    b = make_record(1, run_id="x", decision="needs_info")
    c = make_record(2, run_id="y")
    merged = store.merge_records([a, c], [b])
    assert len(merged) == 2
    assert {r["run_id"]: r["decision"] for r in merged}["x"] == "needs_info"


def test_embed_json_escapes_script_end_and_keeps_order():
    assert "</script>" not in render.embed_json({"t": "</script>"})
    assert render.embed_json({"b": 2, "a": 1}) == '{"b":2,"a":1}'


def test_team_html_fills_placeholders():
    out = render.team_html("__TEAM__|__LABEL__|__DATA__", TEAMS[0], {"a": 1})
    assert out == 'media|Firefox Audio/Video|{"a":1}'


def test_landing_html_without_data():
    out = render.landing_html("__META__ __ROWS__", TEAMS, {})
    assert "no runs yet" in out
    assert 'href="media/index.html"' in out
    assert "1 dashboard<" in out


def test_landing_row_counts_1_week():
    page = stats.team_page(
        [make_record(decision="invalid", resolution="INVALID")],
        datetime(2026, 10, 14, 12, tzinfo=UTC),
    )
    out = render.team_row(1, TEAMS[0], page)
    assert "<strong>1</strong>bugs handled<br>1 closed or moved" in out


LOG_LINE = {
    "run_id": "local-20261015-055005-cf67f6",
    "bug_id": 2080668,
    "review": "posted",
    "posted_at": "2026-10-15T07:06:17Z",
    "applied": [
        {"type": "add_comment+update_bug", "bug_id": 2080668, "ok": True},
        {"type": "update_bug", "bug_id": 1914151, "ok": True},
    ],
    "comment_count": 2,
    "bot_account": "bot@example.com",
}


def test_apply_log_marks_a_posted_run():
    run = make_record(2080668, run_id="local-20261015-055005-cf67f6")
    other = make_record(1, run_id="other")
    out = apply_log([run, other], [LOG_LINE])
    posted = next(r for r in out if r["run_id"] == run["run_id"])
    assert (posted["posted"], posted["outcome"], posted["posted_at"], posted["comment_count"]) == (
        True,
        "posted",
        "2026-10-15T07:06:17Z",
        2,
    )
    assert next(r for r in out if r["run_id"] == "other")["outcome"] is None
    assert "example.com" not in str(out)


def test_apply_log_partly_posted_and_rejected():
    run = make_record(2080668, run_id="local-20261015-055005-cf67f6")
    partly = {
        **LOG_LINE,
        "applied": [{**LOG_LINE["applied"][0]}, {**LOG_LINE["applied"][1], "ok": False}],
    }
    (r,) = apply_log([run], [partly])
    assert (r["posted"], r["outcome"]) == (True, "partly posted")
    (r,) = apply_log([run], [{**LOG_LINE, "review": "rejected", "applied": [], "posted_at": None}])
    assert (r["posted"], r["outcome"]) == (False, "rejected")


def test_apply_log_pending_line_awaits_review():
    run = store.unreviewed(make_record(2080668, run_id="local-20261015-055005-cf67f6"))
    pending = {**LOG_LINE, "review": "pending", "applied": [], "posted_at": None}
    (r,) = apply_log([run], [pending])
    assert (r["posted"], r["rejected"], r["outcome"]) == (False, False, "awaiting review")
    (r,) = apply_log([run], [])
    assert r["outcome"] == "awaiting review"
    (r,) = apply_log([run], [LOG_LINE])
    assert r["outcome"] == "posted"


def test_unreviewed_daily_run_awaits_review_unless_it_failed():
    assert store.unreviewed(make_record())["outcome"] == "awaiting review"
    assert store.unreviewed(make_record(error=True))["outcome"] == "failed"


def test_load_jsonl(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"a": 1}\n\n{"a": 2}\n')
    assert store.load_jsonl(p) == [{"a": 1}, {"a": 2}]
    assert store.load_jsonl(tmp_path / "missing.jsonl") == []


def test_log_teams():
    assert store.log_teams([{"run_id": "a", "inputs": {"team": "media"}}, {"run_id": "b"}]) == {
        "a": "media",
        "b": None,
    }


def test_merge_passes_dedupes_and_keeps_only_safe_fields():
    old = {"team": "media", "at": "2026-10-14T05:40:00+00:00", "selected": 22, "who": "x@y.z"}
    new = [
        {"team": "media", "at": "2026-10-16T05:40:00+00:00", "selected": 0, "who": "x@y.z"},
        {"team": "media", "at": "2026-10-15T05:40:00+00:00", "selected": 3},
        {"team": "media", "at": "2026-10-15T05:40:00+00:00", "selected": 3},
    ]
    merged = store.merge_passes([old], new)
    assert [p["at"][:10] for p in merged] == ["2026-10-14", "2026-10-15", "2026-10-16"]
    assert all(set(p) == {"team", "at", "selected"} for p in merged)


def test_local_team_is_the_log_lines_else_media():
    teams = store.log_teams(
        [{"run_id": "a", "inputs": {"team": "media"}}, {"run_id": "b", "inputs": {"team": None}}]
    )
    assert store.local_team(teams, "a") == "media"
    assert store.local_team(teams, "b") is None
    assert store.local_team(teams, "awaiting-review") == "media"


def test_only_the_media_team_is_shown():
    assert is_shown("media")
    assert not is_shown(None)
    assert not is_shown("graphics")


def test_shown_drops_runs_of_no_team_or_another_team():
    records = [make_record(1, team="media"), make_record(2, team=None), make_record(3, team="gfx")]
    assert [r["bug_id"] for r in store.shown(records)] == [1]


def test_apply_issue_types_fills_only_runs_without_a_type():
    old = make_record(1, run_id="a")
    own = make_record(2, run_id="b", issue_type="drm")
    lines = [
        {
            "run_id": "a",
            "issue_type": "other",
            "note": "wake lock, ask x@y.z",
            "source": "backfill",
        },
        {"run_id": "b", "issue_type": "capture", "source": "backfill"},
    ]
    a, b = store.apply_issue_types([old, own], lines)
    assert (a["issue_type"], b["issue_type"]) == ("other", "drm")
    assert "x@y.z" not in a["issue_type_note"]
    (c,) = store.apply_issue_types([make_record(3, run_id="c")], lines)
    assert c["issue_type"] is None
