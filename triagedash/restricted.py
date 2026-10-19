"""Keeps restricted bugs off the public page.

A run names bugs: its own, and others in its fields (a regressor, a blocked bug, a
duplicate target, a meta bug) and in any of its strings, where every 5 to 8 digit number
counts that stands alone or follows "bug" or "bmo" (so `D334987`, a revision, does not).
The page keeps a bug only if an anonymous Bugzilla read can see it, the same filter
Bugzilla applies to readers without editbugs. A run on a hidden bug is dropped; any other
hidden bug is taken out of the fields, and becomes "a restricted bug" in the text.
"""

from __future__ import annotations

import re

HIDDEN = "a restricted bug"
# Strings that hold no bug number but can hold long digit runs.
NOT_TEXT = ("run_id", "started_at", "filed", "posted_at")
_PREFIX = r"(?i:\b(?:bugs?|bmo)\s*#?\s*)"
_ALONE = r"(?<![\w.])"
_NUMBER = re.compile(rf"(?:{_PREFIX}|{_ALONE})(\d{{5,8}})(?![\w])")
_LINK = r"(?:https?://)?(?:bugzilla\.mozilla\.org/(?:show_bug\.cgi\?(?:[\w=]*&)?id=)?|bugzil\.la/)"


def strings(value) -> list[str]:
    """Every string in a value, at any depth."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    return []


def text_of(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in NOT_TEXT and strings(v)}


def named_bugs(record: dict) -> set[int]:
    """Every bug the record names, its own included."""
    ids = {record["bug_id"], *record["blocks_add"], *record["regressed_by_add"]}
    if record["dupe_of"]:
        ids.add(record["dupe_of"])
    for o in record["other_bugs"]:
        ids |= {o["bug_id"], *o["blocks_add"]}
    return ids | {int(n) for s in strings(text_of(record)) for n in _NUMBER.findall(s)}


def all_named(records: list[dict]) -> set[int]:
    return set().union(*map(named_bugs, records))


# Bug ids grow by about 15,000 a month, so a number this far above the newest bug a run is
# about is no bug yet, such as a duration in milliseconds.
ID_MARGIN = 100_000


def hidden_bugs(named: set[int], visible: set[int], own: set[int]) -> set[int]:
    """The named bugs to take out: every one an anonymous read cannot see, except numbers
    too high to be a bug. Bugzilla answers the same for a restricted and a missing bug, so
    a missing bug is hidden too, which can only hide too much."""
    ceiling = max(own, default=0) + ID_MARGIN
    return {b for b in named - visible if b <= ceiling}


def redact_text(text: str, hidden: set[int]) -> str:
    """Replaces each mention of a hidden bug, with its link or its "bug" word."""
    ids = "|".join(map(str, sorted(hidden)))
    text = re.sub(rf"\[[^\]]*\]\({_LINK}(?:{ids})(?!\d)[^)]*\)", HIDDEN, text)
    text = re.sub(rf"{_LINK}(?:{ids})(?!\d)(?:#c\d+)?", HIDDEN, text)
    return re.sub(rf"(?:{_PREFIX}|{_ALONE})(?:{ids})(?![\w])", HIDDEN, text)


def redact_value(value, hidden: set[int]):
    if isinstance(value, str):
        return redact_text(value, hidden)
    if isinstance(value, list):
        return [redact_value(v, hidden) for v in value]
    if isinstance(value, dict):
        return {k: redact_value(v, hidden) for k, v in value.items()}
    return value


def redact(record: dict, hidden: set[int]) -> dict:
    """The record with every hidden bug taken out of its fields and its strings."""

    def keep(ids: list[int]) -> list[int]:
        return [b for b in ids if b not in hidden]

    out = {
        **record,
        "blocks_add": keep(record["blocks_add"]),
        "regressed_by_add": keep(record["regressed_by_add"]),
        "dupe_of": None if record["dupe_of"] in hidden else record["dupe_of"],
        "other_bugs": [
            {**o, "blocks_add": keep(o["blocks_add"])}
            for o in record["other_bugs"]
            if o["bug_id"] not in hidden
        ],
    }
    return {**out, **redact_value(text_of(out), hidden)}


def redact_all(records: list[dict], hidden: set[int]) -> list[dict]:
    """Drops the runs on hidden bugs, and takes every other hidden bug out of the rest."""
    if not hidden:
        return records
    return [redact(r, hidden) for r in records if r["bug_id"] not in hidden]
