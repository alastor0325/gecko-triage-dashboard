import json

import pytest

from triagedash import hackbot, store

RUN = {
    "run_id": "11111111-2222-4333-8444-555555555555",
    "agent": "gecko-triage",
    "status": "succeeded",
    "inputs": {"bug_id": 2080668, "team": "media"},
    "requested_by": "someone@example.com",
    "artifacts": ["logs/agent.log"],
    "created_at": "2026-10-20T06:00:00+00:00",
    "updated_at": "2026-10-20T06:10:00+00:00",
    "summary": {"status": "ok", "error": None, "findings": {"bug_id": 2080668}, "actions": []},
}
APPLIED = {
    "idx": 0,
    "type": "bugzilla.add_comment",
    "status": "applied",
    "applied_at": "2026-10-20T08:00:00+00:00",
}
PENDING = {"idx": 0, "type": "bugzilla.add_comment", "status": "pending", "applied_at": None}
FAILED = {"idx": 1, "type": "bugzilla.update_bug", "status": "failed", "applied_at": None}


def test_key_from_file(tmp_path):
    key = tmp_path / "key"
    assert hackbot.key_from_file(key) is None
    key.write_text("secret\n")
    key.chmod(0o644)
    with pytest.raises(hackbot.KeyFileError):
        hackbot.key_from_file(key)
    key.chmod(0o600)
    assert hackbot.key_from_file(key) == "secret"


def test_settled():
    assert not hackbot.settled({"status": "running"}, [])
    assert hackbot.settled({"status": "failed"}, [])
    assert not hackbot.settled({"status": "succeeded"}, [])  # not applied yet
    assert not hackbot.settled({"status": "succeeded"}, [PENDING])
    assert hackbot.settled({"status": "succeeded"}, [APPLIED, FAILED])


def test_slim_drops_email_and_artifacts():
    assert not {"requested_by", "artifacts"} & set(hackbot.slim(RUN))


def test_day_of_is_utc():
    assert hackbot.day_of({"created_at": "2026-10-20T23:30:00-07:00"}) == "2026-10-21"


def test_outcome_uses_the_local_words():
    out = hackbot.outcome
    assert out(RUN, [], None)["outcome"] == "awaiting review"
    assert out(RUN, [PENDING], None)["outcome"] == "awaiting review"
    posted = out(RUN, [APPLIED], None)
    assert (posted["outcome"], posted["posted"], posted["posted_at"]) == (
        "posted",
        True,
        APPLIED["applied_at"],
    )
    assert out(RUN, [APPLIED, FAILED], None)["outcome"] == "partly posted"
    assert out(RUN, [FAILED], None)["outcome"] == "apply failed"
    assert out({**RUN, "status": "timed_out"}, [], None)["outcome"] == "failed"
    rejected = {"run_id": RUN["run_id"], "review": "rejected"}
    r = out(RUN, [PENDING], rejected)
    assert (r["outcome"], r["rejected"], r["posted"], r["pending_actions"]) == (
        "rejected",
        True,
        False,
        1,
    )
    conflict = out(RUN, [APPLIED], rejected)
    assert (conflict["outcome"], conflict["rejected"]) == ("posted", True)


def test_reject_and_load_reviews(tmp_path):
    hackbot.reject(tmp_path, "a", "wrong S/P", "2026-10-20T09:00:00+00:00")
    assert hackbot.load_reviews(tmp_path)["a"]["reason"] == "wrong S/P"


def test_latest_reviews():
    lines = [
        {"run_id": "a", "review": "rejected", "at": "2026-10-20T09:00:00+00:00"},
        {"run_id": "a", "review": "approved", "at": "2026-10-20T08:00:00+00:00"},
    ]
    assert hackbot.latest_reviews(lines)["a"]["review"] == "rejected"


def test_fetch_pages_until_known_and_refetches_unsettled(tmp_path):
    old = {**RUN, "run_id": "old", "created_at": "2026-10-19T06:00:00+00:00"}
    held = {**RUN, "run_id": "held", "created_at": "2026-10-19T07:00:00+00:00"}
    for doc, actions in ((old, [APPLIED]), (held, [PENDING])):
        path = tmp_path / "2026-10-19" / f"{doc['run_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"run": hackbot.slim(doc), "actions": actions}))
    new = {**RUN, "run_id": "new"}
    calls = []

    def get(path):
        calls.append(path)
        if path.startswith("/runs?"):
            return [new, held, old]
        rid = path.split("/")[2]
        if path.endswith("/actions"):
            return [APPLIED] if rid == "held" else []
        return {"new": new, "held": held}[rid]

    assert hackbot.fetch(get, tmp_path, "2026-10-20T10:00:00+00:00") == 2
    assert not any("artifacts" in c for c in calls)
    assert sum(c.startswith("/runs?") for c in calls) == 1
    written = json.loads((tmp_path / "2026-10-20" / "new.json").read_text())
    assert "requested_by" not in written["run"]
    assert json.loads((tmp_path / "2026-10-19" / "held.json").read_text())["actions"] == [APPLIED]
    assert "someone@example.com" not in (tmp_path / "2026-10-20" / "new.json").read_text()


META = {
    "creator": "r@example.com",
    "assigned_to": "",
    "product": "Core",
    "component": "Widget: Gtk",
    "summary": "Title",
    "groups": [],
    "creation_time": "2026-10-10T00:00:00Z",
}


def test_to_record_maps_a_hackbot_run():
    doc = {"run": hackbot.slim(RUN), "actions": [PENDING]}
    r = hackbot.to_record(doc, META, users={}, review=None)
    assert (r["source"], r["run_id"], r["bug_id"], r["team"]) == (
        "hackbot",
        RUN["run_id"],
        2080668,
        "media",
    )
    assert r["started_at"] == RUN["created_at"]
    assert (r["outcome"], r["posted"], r["pending_actions"], r["rejected"]) == (
        "awaiting review",
        False,
        1,
        False,
    )


def test_to_record_failed_run_is_an_error():
    doc = {
        "run": {**hackbot.slim(RUN), "status": "failed", "summary": {"traceback": "x"}},
        "actions": [],
    }
    r = hackbot.to_record(doc, META, users={}, review=None)
    assert (r["error"], r["outcome"]) == (True, "failed")


def test_records_keep_public_runs_and_their_team():
    def doc(run_id, bug_id, team):
        run = {**hackbot.slim(RUN), "run_id": run_id, "inputs": {"bug_id": bug_id, "team": team}}
        return {"run": run, "actions": [PENDING]}

    docs = [doc("a", 1, "media"), doc("b", 1, None), doc("c", 1, "graphics"), doc("d", 2, "media")]
    metas = {1: META, 2: {**META, "groups": ["core-security"]}}
    out = hackbot.records(docs, metas, {}, {})
    assert [(r["run_id"], r["team"]) for r in out] == [
        ("a", "media"),
        ("b", None),
        ("c", "graphics"),
    ]
    assert [r["run_id"] for r in store.shown(out)] == ["a"]
