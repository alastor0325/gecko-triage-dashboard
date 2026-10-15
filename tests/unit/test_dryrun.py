from datetime import timedelta, timezone

from triagedash.dryrun import (
    EMAIL,
    clean_real_name,
    is_public,
    needinfo_role,
    orphan_bugs,
    parse_summary,
    requestees,
    run_started_at,
    scrub,
    strip_footer,
    summary_bug_id,
)

from .conftest import make_record, make_summary


def parse(summary, meta, bug_id=100):
    return parse_summary(
        summary, bug_id=bug_id, run_id="local-20261014-174025-eb0234", meta=meta, users={}
    )


def test_run_started_at_is_utc():
    taipei = timezone(timedelta(hours=8))
    assert run_started_at("local-20261014-174025-eb0234", taipei) == "2026-10-14T09:40:25+00:00"
    assert run_started_at("local-20261014-174025-eb0234").endswith("+00:00")
    assert run_started_at("something-else") is None


def test_scrub_walks_dicts():
    assert scrub({"a": ["x@example.com"], "b": {"c": ":jdoe"}}) == {
        "a": ["[email]"],
        "b": {"c": ":[person]"},
    }


def test_scrub_removes_emails_and_mentions():
    assert scrub("ask a@b.example.org and :jdoe now") == "ask [email] and :[person] now"
    assert scrub(["x@example.com", 3]) == ["[email]", 3]
    assert scrub(None) is None


def test_scrub_keeps_about_pages_and_urls():
    assert scrub("attach about:support and about:memory") == "attach about:support and about:memory"
    assert scrub("see https://example.org:8080/x") == "see https://example.org:8080/x"
    assert scrub("(:jdoe)") == "(:[person])"


def test_needinfo_role(meta):
    assert needinfo_role("reporter@example.com", meta) == "reporter"
    assert needinfo_role("dev@example.com", meta) == "assignee"
    assert needinfo_role("x@example.com", meta) == "other"
    assert needinfo_role(None, meta) == "unknown"


def test_record_holds_no_email_in_any_field(meta):
    changes = {"flags": [{"name": "needinfo", "status": "?", "requestee": "reporter@example.com"}]}
    summary = make_summary(changes=changes, comment="Asked x@example.com.")
    record = parse(summary, {**meta, "summary": "Crash, cc z@example.com"})
    assert record["needinfo"] == [{"role": "reporter", "name": None, "nick": None}]
    assert not EMAIL.search(str(record))


def test_record_keys_match_the_test_factory(meta):
    assert set(parse(make_summary(), meta)) == set(make_record())


def test_parse_fields(meta):
    changes = {
        "severity": "S3",
        "priority": "P3",
        "blocks": {"add": [5]},
        "keywords": {"add": ["regression"]},
        "regressed_by": {"add": [7]},
    }
    r = parse(make_summary(decision="triaged", changes=changes), meta)
    assert (
        r["severity"],
        r["priority"],
        r["blocks_add"],
        r["keywords_add"],
        r["regressed_by_add"],
    ) == ("S3", "P3", [5], ["regression"], [7])
    assert r["started_at"].endswith("+00:00")
    assert r["team"] == "media"
    assert r["posted"] is False
    assert r["error"] is False
    assert r["move_to"] is None


def test_team_comes_from_component(meta):
    assert parse(make_summary(), {**meta, "component": "Graphics"})["team"] is None


def test_parse_duplicate_with_meta_bug_on_dupe_target(meta):
    s = make_summary(
        decision="duplicate",
        changes={"status": "RESOLVED", "resolution": "DUPLICATE", "dupe_of": 9},
    )
    s["actions"].append(
        {
            "type": "bugzilla.update_bug",
            "params": {"bug_id": 9, "changes": {"blocks": {"add": [42]}}},
        }
    )
    r = parse(s, meta)
    assert (r["resolution"], r["dupe_of"]) == ("DUPLICATE", 9)
    assert r["blocks_add"] == []
    assert r["other_bugs"] == [{"bug_id": 9, "blocks_add": [42]}]


def test_parse_move(meta):
    r = parse(make_summary(decision="wrong_component", changes={"component": "Web Audio"}), meta)
    assert r["move_to"] == "Core :: Web Audio"


def test_crashed_run(meta):
    r = parse({"traceback": "boom"}, meta, bug_id=77)
    assert r["bug_id"] == 77
    assert r["error"] is True
    assert r["decision"] is None


def test_summary_bug_id_and_orphans():
    done = [{"findings": {"bug_id": 1}}, {"traceback": "boom"}]
    assert summary_bug_id(done[0]) == 1
    assert summary_bug_id(done[1]) is None
    assert orphan_bugs([1, 2], done) == {2}
    assert orphan_bugs([1, 2, 3], done) == {2, 3}
    assert orphan_bugs([1], done) == set()


def test_is_public(meta):
    assert is_public(meta)
    assert not is_public({**meta, "groups": ["media-core-security"]})


def test_scrub_keeps_cpp_scopes():
    assert (
        scrub("Crash in [@ mozilla::MozPromise<T>::Resolve]")
        == "Crash in [@ mozilla::MozPromise<T>::Resolve]"
    )


def test_parse_keeps_the_comment_scrubbed(meta):
    r = parse(make_summary(comment="Thanks. Please ask x@example.com or :jdoe."), meta)
    assert r["comment"] == "Thanks. Please ask [email] or :[person]."
    assert parse({"traceback": "boom"}, meta)["comment"] is None


def test_strip_footer():
    text = (
        "Thanks.\n\n---\n\nKeep this.\n\n---\n\n"
        "If you'd like to give feedback on this comment...\n\n"
        "gecko-triage · rules 0.1.0 · asked: none · unread: none"
    )
    assert strip_footer(text) == "Thanks.\n\n---\n\nKeep this."
    assert strip_footer("No footer here.") == "No footer here."
    assert (
        strip_footer("Body.\n\n---\n\nA normal last section.")
        == "Body.\n\n---\n\nA normal last section."
    )
    old_agent_name = "Body.\n\n---\n\nmedia-triage · rules 0.1.0 · asked: none · unread: none"
    assert strip_footer(old_agent_name) == "Body."
    assert strip_footer(None) is None


def test_clean_real_name():
    assert clean_real_name("Pat Doe [:pdoe] (PTO)") == "Pat Doe"
    assert clean_real_name(":pdoe") is None
    assert clean_real_name("") is None
    assert clean_real_name(None) is None


def test_requestees():
    s = make_summary(changes={"flags": [{"name": "needinfo", "requestee": "a@example.com"}]})
    s["actions"].append(
        {
            "type": "bugzilla.update_bug",
            "params": {
                "bug_id": 9,
                "changes": {"flags": [{"name": "needinfo", "requestee": "b@example.com"}]},
            },
        }
    )
    assert requestees(s, 100) == {"a@example.com"}
    assert requestees({"traceback": "x"}, 100) == set()


def test_needinfo_gets_the_public_name_and_keeps_its_nick(meta):
    changes = {"flags": [{"name": "needinfo", "status": "?", "requestee": "dev@example.com"}]}
    users = {"dev@example.com": {"real_name": "Pat Doe [:pdoe]", "nick": "pdoe"}}
    summary = make_summary(changes=changes)
    r = parse_summary(
        summary, bug_id=100, run_id="local-20261014-174025-eb0234", meta=meta, users=users
    )
    assert r["needinfo"] == [{"role": "assignee", "name": "Pat Doe", "nick": "pdoe"}]
    assert "example.com" not in str(r)


def test_strip_footer_new_form_without_agent_footer():
    text = (
        "Thanks.\n\n---\n\nKeep this.\n\n---\n\n"
        "To give feedback on this comment, add a thumbs-up or thumbs-down reaction."
    )
    assert strip_footer(text) == "Thanks.\n\n---\n\nKeep this."
