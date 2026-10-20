"""Proposed whiteboard fix tags, from a tag-only check of the analyzed bugs.

gecko-triage writes `~/hackbot/pilot/fix-tags-<YYYY-MM-DD>.jsonl`, one line per bug. It is
a proposal: nothing is on Bugzilla. Only the bug and its known tags are kept: the page
shows the tags alone.
"""

from __future__ import annotations

from pathlib import Path

# Each known whiteboard tag and its short label on the page.
LABELS = {"[gecko-triage:easy-fix]": "easy fix?", "[gecko-triage:gfb-candidate]": "gfb?"}


def latest(pilot: Path) -> Path | None:
    """The newest proposal file, by the date in its name."""
    files = sorted(pilot.glob("fix-tags-*.jsonl"))
    return files[-1] if files else None


def posted(whiteboard: str | None) -> list[str]:
    """The known tags already on a bug's whiteboard."""
    return [t for t in LABELS if t in (whiteboard or "")]


def clean(line: dict) -> dict:
    """A proposal line with only the bug and its known tags."""
    return {"bug_id": line["bug_id"], "tags": [t for t in line.get("tags") or [] if t in LABELS]}
