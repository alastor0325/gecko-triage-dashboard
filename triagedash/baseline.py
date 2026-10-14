"""The local /triage drafts, used as the reference for dry-run agreement.

The categories follow `~/hackbot/compare.py`, a local script that cannot be imported."""

from __future__ import annotations

AGENT_CATEGORY = {
    "needs_info": "needs-info",
    "triaged": "analyzed",
    **dict.fromkeys(
        ("duplicate", "invalid", "wrong_component", "incomplete", "stalled"), "close-or-move"
    ),
}


def triage_category(draft: dict) -> str:
    """Close or move, else needs info, else analyzed."""
    if draft.get("resolution") or draft.get("component"):
        return "close-or-move"
    if draft.get("ni_targets") and not draft.get("severity"):
        return "needs-info"
    return "analyzed"


def agent_category(decision: str | None) -> str | None:
    """Unknown decisions pass through, so a new value shows instead of being miscounted."""
    return AGENT_CATEGORY.get(decision, decision)


def baseline_entry(draft: dict) -> dict:
    """Keeps only fields with no person in them."""
    return {
        "category": triage_category(draft),
        "severity": draft.get("severity"),
        "priority": draft.get("priority"),
        "resolution": draft.get("resolution"),
        "dupe_of": int(draft["dupe_of"]) if draft.get("dupe_of") else None,
        "needinfo_count": len(draft.get("ni_targets") or []),
    }
