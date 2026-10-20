from triagedash import fixtags
from triagedash.__main__ import proposal


def test_clean_keeps_only_known_tags_and_the_bug():
    line = {"bug_id": 1, "tags": ["[gecko-triage:easy-fix]", "[x]"], "reason": "see bug 2"}
    assert fixtags.clean(line) == {"bug_id": 1, "tags": ["[gecko-triage:easy-fix]"]}


def test_posted_tags_leave_the_proposal():
    assert fixtags.posted("[gecko-triage:easy-fix] [foo]") == ["[gecko-triage:easy-fix]"]
    assert fixtags.posted(None) == []
    fix = {1: {"bug_id": 1, "tags": ["[gecko-triage:easy-fix]"]}}
    on_bug = {1: {"fix_tags": ["[gecko-triage:easy-fix]"]}}
    assert proposal(fix, on_bug, {"bug_id": 1})["tags"] == []
    assert proposal(fix, {}, {"bug_id": 1})["tags"] == ["[gecko-triage:easy-fix]"]
    assert proposal(fix, {}, {"bug_id": 2}) is None
    both = {1: {"bug_id": 1, "tags": list(fixtags.LABELS)}}
    gfb_posted = {1: {"fix_tags": ["[gecko-triage:gfb-candidate]"]}}
    assert proposal(both, gfb_posted, {"bug_id": 1})["tags"] == []


def test_latest_picks_the_newest_file(tmp_path):
    assert fixtags.latest(tmp_path) is None
    for d in ("2026-10-19", "2026-10-20"):
        (tmp_path / f"fix-tags-{d}.jsonl").write_text("")
    assert fixtags.latest(tmp_path).name == "fix-tags-2026-10-20.jsonl"
