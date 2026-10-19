from triagedash import restricted

from .conftest import make_record


def test_named_bugs_reads_fields_and_every_string():
    r = make_record(
        100,
        run_id="local-20261018-180626-cd83c5",
        blocks_add=[1445470],
        regressed_by_add=[1999901],
        dupe_of=2083234,
        other_bugs=[{"bug_id": 2083234, "blocks_add": [1665980]}],
        title="Crash, see Bug #1318196",
        comment="bmo#2067742 and https://bugzilla.mozilla.org/show_bug.cgi?id=1999999.",
        issue_type_note="like bugzil.la/1885268",
        asked=["bug2000001 profile", "D334987 in review"],
    )
    assert restricted.named_bugs(r) == {
        100, 1445470, 1999901, 2083234, 1665980, 1318196, 2067742, 1999999, 1885268, 2000001,
    }  # fmt: skip


def test_hidden_bugs_keeps_numbers_too_high_to_be_bugs():
    named = {1999901, 1445470, 9999999}
    hidden = restricted.hidden_bugs(named, visible={1445470}, own={2083754})
    assert hidden == {1999901}


def test_redact_takes_hidden_bugs_out_of_fields_and_text():
    r = make_record(
        100,
        blocks_add=[1445470, 1999901],
        regressed_by_add=[1999901],
        dupe_of=1999901,
        other_bugs=[
            {"bug_id": 1999901, "blocks_add": []},
            {"bug_id": 7, "blocks_add": [1999901]},
        ],
        title="Like bug1999901",
        comment="A regression from Bug #1999901, see [the fix](https://bugzil.la/1999901) "
        "and https://bugzilla.mozilla.org/show_bug.cgi?id=1999901#c3, bmo#1999901 and "
        "1999901. Bug 1445470 took 60000 ms; D1999901 is a revision.",
    )
    (out,) = restricted.redact_all([r], hidden={1999901})
    assert out["blocks_add"] == [1445470]
    assert out["regressed_by_add"] == []
    assert out["dupe_of"] is None
    assert out["other_bugs"] == [{"bug_id": 7, "blocks_add": []}]
    assert "1999901" not in str(out).replace("D1999901", "")
    assert out["title"] == "Like a restricted bug"
    assert out["comment"] == (
        "A regression from a restricted bug, see a restricted bug and a restricted bug, "
        "a restricted bug and a restricted bug. Bug 1445470 took 60000 ms; D1999901 is a "
        "revision."
    )
    assert out["run_id"] == r["run_id"]


def test_redact_all_drops_runs_on_hidden_bugs():
    a, b = make_record(1), make_record(1999901)
    assert restricted.redact_all([a, b], hidden={1999901}) == [a]
    assert restricted.redact_all([a], hidden=set()) == [a]
