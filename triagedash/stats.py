"""Shapes one team's records into the page data. Pure: no I/O.

The page picks, per bug, the newest run inside the chosen window or round, so the data
holds every run that changed a bug, newest first."""

from __future__ import annotations

from datetime import datetime, timedelta

from .store import when

# Most harmful first: a wrong close hides a real bug, a wrong move takes it off the
# team, a wrong S/P misplaces it, and a needinfo only waits on someone.
CATEGORIES = ("closed", "moved", "sp", "needinfo")


def categories(record: dict) -> list[str]:
    flags = {
        "closed": bool(record["resolution"]),
        "moved": bool(record["move_to"]),
        "sp": bool(record["severity"] or record["priority"]),
        "needinfo": bool(record["needinfo"]),
    }
    return [c for c in CATEGORIES if flags[c]]


# The page's time windows, in days. The start of each is computed once, here.
WINDOWS = {"7d": 7, "30d": 30}
NEW_DAYS = 7


def tags(record: dict) -> list[str]:
    """Tags that hold for the run itself. `again` depends on the run that the page
    picks, so the page adds it."""
    out = []
    if "regression" in record["keywords_add"] or record["regressed_by_add"]:
        out.append("regression")
    if any(role != "reporter" for role in record["needinfo"]):
        out.append("dev needinfo")
    return out


def window_starts(as_of: datetime) -> dict[str, str]:
    return {k: (as_of - timedelta(days=d)).isoformat() for k, d in WINDOWS.items()}


def is_new(filed: str | None, as_of: datetime) -> bool:
    """Filed in the last NEW_DAYS days."""
    return bool(filed) and as_of - datetime.fromisoformat(filed) <= timedelta(days=NEW_DAYS)


def acted(record: dict) -> bool:
    """A run that changed the bug. Failed and preflight-skipped runs changed nothing."""
    return not record["error"] and record["decision"] != "skipped" and bool(record["started_at"])


def run_view(record: dict) -> dict:
    keep = (
        "posted", "round", "started_at", "summary", "severity", "priority", "needinfo",
        "resolution", "dupe_of", "move_to", "blocks_add", "keywords_add", "regressed_by_add",
        "other_bugs",
    )  # fmt: skip
    return {**{k: record[k] for k in keep}, "categories": categories(record), "tags": tags(record)}


def bugs(records: list[dict], as_of: datetime) -> list[dict]:
    """Each bug the bot changed, with all its runs newest first. Title and the `new` tag come
    from the newest run."""
    by_bug: dict[int, list[dict]] = {}
    for r in sorted(filter(acted, records), key=lambda r: (when(r), r["run_id"]), reverse=True):
        by_bug.setdefault(r["bug_id"], []).append(r)
    return [
        {
            "bug_id": bug_id,
            "title": runs[0]["title"],
            "tags": ["new"] if is_new(runs[0]["filed"], as_of) else [],
            "runs": [run_view(r) for r in runs],
        }
        for bug_id, runs in by_bug.items()
    ]


def rounds(records: list[dict]) -> list[str]:
    """Each round that changed a bug, newest first by its first run. Runs without a round
    (posted runs) are not listed."""
    first: dict[str, str] = {}
    for r in filter(acted, records):
        if r["round"]:
            first[r["round"]] = min(first.get(r["round"], r["started_at"]), r["started_at"])
    return sorted(first, key=first.get, reverse=True)


def recent_counts(page: dict) -> dict:
    """For the landing page: bugs changed in the 7-day window, and how many of them the
    newest such run closed or moved."""
    start = page["windows"]["7d"]
    newest = [next((r for r in b["runs"] if r["started_at"] >= start), None) for b in page["bugs"]]
    shown = [r for r in newest if r]
    closed_or_moved = sum(bool({"closed", "moved"} & set(r["categories"])) for r in shown)
    return {"bugs": len(shown), "closed_or_moved": closed_or_moved}


def team_page(records: list[dict], as_of: datetime) -> dict:
    """Records are one team's."""
    return {
        "as_of": as_of.isoformat(),
        "posted": any(r["posted"] for r in records),
        "categories": list(CATEGORIES),
        "windows": window_starts(as_of),
        "rounds": rounds(records),
        "bugs": bugs(records, as_of),
    }
