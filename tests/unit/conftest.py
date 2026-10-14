import pytest

META = {
    "creator": "reporter@example.com",
    "assigned_to": "dev@example.com",
    "product": "Core",
    "component": "Audio/Video: Playback",
    "summary": "Video stalls after seek",
    "groups": [],
}


def make_summary(
    bug_id=100, decision="needs_info", changes=None, comment="Please attach a profile.", **findings
):
    return {
        "status": "ok",
        "error": None,
        "findings": {
            "bug_id": bug_id,
            "decision": decision,
            "summary": "Stall after seek.",
            "asked": ["profile"],
            "num_turns": 10,
            "total_cost_usd": 0.5,
            "auto_apply": True,
            **findings,
        },
        "actions": [
            {"type": "bugzilla.add_comment", "params": {"bug_id": bug_id, "text": comment}},
            {"type": "bugzilla.update_bug", "params": {"bug_id": bug_id, "changes": changes or {}}},
        ],
    }


def make_record(bug_id=100, started_at="2026-10-14T10:00:00+00:00", run_id=None, **overrides):
    record = {
        "posted": False,
        "round": "r1",
        "run_id": run_id or f"local-{bug_id}-{started_at}",
        "started_at": started_at,
        "bug_id": bug_id,
        "title": "t",
        "filed": "2026-10-10T00:00:00Z",
        "team": "media",
        "error": False,
        "decision": "triaged",
        "summary": "s",
        "severity": None,
        "priority": None,
        "needinfo": [],
        "blocks_add": [],
        "keywords_add": [],
        "regressed_by_add": [],
        "move_to": None,
        "resolution": None,
        "dupe_of": None,
        "other_bugs": [],
    }
    record.update(overrides)
    return record


@pytest.fixture
def meta():
    return dict(META)
