from triagedash import fixtags


def test_clean_keeps_only_known_tags_and_the_bug():
    line = {"bug_id": 1, "tags": ["[gecko-triage:easy-fix]", "[x]"], "reason": "see bug 2"}
    assert fixtags.clean(line) == {"bug_id": 1, "tags": ["[gecko-triage:easy-fix]"]}


def test_whiteboard_tags_replace_the_proposal():
    assert fixtags.posted("[gecko-triage:easy-fix] [foo]") == ["[gecko-triage:easy-fix]"]
    assert fixtags.posted(None) == []
    easy = {"bug_id": 1, "tags": ["[gecko-triage:easy-fix]"]}
    both = {"bug_id": 1, "tags": list(fixtags.LABELS)}
    on_bug = {"fix_tags": ["[gecko-triage:easy-fix]"]}
    assert fixtags.shown(easy, on_bug) == {"tags": ["[gecko-triage:easy-fix]"], "on_bugzilla": True}
    assert fixtags.shown(easy, {}) == {"tags": ["[gecko-triage:easy-fix]"], "on_bugzilla": False}
    assert fixtags.shown(None, on_bug)["on_bugzilla"] is True
    assert fixtags.shown(None, {}) is None
    gfb_on_bug = {"fix_tags": ["[gecko-triage:gfb-candidate]"]}
    assert fixtags.shown(both, gfb_on_bug)["tags"] == ["[gecko-triage:gfb-candidate]"]


def test_latest_picks_the_newest_file(tmp_path):
    assert fixtags.latest(tmp_path) is None
    for d in ("2026-10-19", "2026-10-20"):
        (tmp_path / f"fix-tags-{d}.jsonl").write_text("")
    assert fixtags.latest(tmp_path).name == "fix-tags-2026-10-20.jsonl"


def test_the_newest_run_tags_win_over_the_file():
    line = {"bug_id": 1, "tags": []}
    assert fixtags.proposal(["[gecko-triage:easy-fix]"], line) == {
        "tags": ["[gecko-triage:easy-fix]"]
    }
    assert fixtags.proposal([], line) == {"tags": []}
    assert fixtags.proposal(None, line) == line
    assert fixtags.proposal(None, None) is None
