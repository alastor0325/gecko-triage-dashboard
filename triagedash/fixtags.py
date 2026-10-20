"""Whiteboard fix tags: posted on a bug's whiteboard, or proposed by a tag-only check.

gecko-triage writes its proposals to `~/hackbot/pilot/fix-tags-<YYYY-MM-DD>.jsonl`, one
line per bug; only the bug and its known tags are kept. The daily refresh reads which
tags are on each bug's whiteboard, and those win over the proposal.
"""

from __future__ import annotations

from pathlib import Path

# Each known whiteboard tag, strongest last, with its short label (list rows) and its
# full label (card). A gfb candidate is always an easy fix too, so the page shows only the
# strongest tag.
LABELS = {
    "[gecko-triage:easy-fix]": {"short": "easy fix", "full": "easy fix"},
    "[gecko-triage:gfb-candidate]": {"short": "gfb", "full": "good first bug"},
}


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


def shown(proposal: dict | None, state: dict) -> dict | None:
    """The fix tags a bug shows: the ones on its whiteboard once any gecko-triage fix tag
    is there, even a weaker one than proposed, else the proposed ones. If the whiteboard
    tag is removed later, the proposal shows again while the newest file still holds it."""
    if state.get("fix_tags"):
        return {"tags": state["fix_tags"], "on_bugzilla": True}
    return proposal and {"tags": proposal["tags"], "on_bugzilla": False}
