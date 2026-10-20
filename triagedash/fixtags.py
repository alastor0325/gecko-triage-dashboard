"""Proposed whiteboard fix tags, from a tag-only check of the analyzed bugs.

gecko-triage writes `~/hackbot/pilot/fix-tags-<YYYY-MM-DD>.jsonl`, one line per bug. It is
a proposal: nothing is on Bugzilla. Only the known tags and the fields the page shows are
kept, and every string is scrubbed as the runs are.
"""

from __future__ import annotations

from pathlib import Path

from .summary import scrub

TAGS = ("[gecko-triage:easy-fix]", "[gecko-triage:gfb-candidate]")
FIELDS = ("reason", "failed_conditions", "patch", "cause_file")


def latest(pilot: Path) -> Path | None:
    """The newest proposal file, by the date in its name."""
    files = sorted(pilot.glob("fix-tags-*.jsonl"))
    return files[-1] if files else None


def clean(line: dict) -> dict:
    """A proposal line with only the known tags and the shown fields, scrubbed."""
    return {
        "bug_id": line["bug_id"],
        "tags": [t for t in line.get("tags") or [] if t in TAGS],
        **{k: scrub(line.get(k)) for k in FIELDS},
    }
