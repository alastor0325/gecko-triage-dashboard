from datetime import UTC, datetime

from triagedash import render, stats, store
from triagedash.teams import TEAMS

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
    assert "<strong>1</strong>bugs handled in 1 week · 1 closed or reassigned" in out
