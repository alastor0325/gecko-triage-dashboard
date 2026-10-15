"""Shapes one team's records into the page data. Pure: no I/O.

The page shows, per bug, its newest run and the earlier runs that were posted. Every
date the page shows, including the per-day chart, is in the viewer's time zone, so the
page buckets runs into days itself."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from .markdown import render
from .store import order

# The agent's decision, grouped as the local triage dashboard groups its drafts.
CATEGORY = {
    "triaged": "analyzed",
    "needs_info": "needs-info",
    **dict.fromkeys(("duplicate", "invalid", "wrong_component", "incomplete", "stalled"), "close"),
}
# Tab order, as in the triage dashboard, with each tab's label and chart color. The colors
# are COLOR_NAVY, COLOR_MUSTARD and COLOR_RED of the review-stats editorial palette.
CATEGORIES = ("analyzed", "needs-info", "close")
CATEGORY_LABEL = {"analyzed": "Analyzed", "needs-info": "Needs info", "close": "Close / Reassign"}
CATEGORY_COLOR = {"analyzed": "#1B3B6F", "needs-info": "#C89B3C", "close": "#FF0039"}
DECISION_LABEL = {"triaged": "analyzed"}
# Most harmful first, for the list: a wrong close or move takes a bug off the team,
# a wrong S/P misplaces it, and a needinfo only waits on someone.
RISK = ("close", "analyzed", "needs-info")
# key: (days, label), as the review-stats period toggle.
PERIODS = {"1w": (7, "1-Week"), "1m": (30, "1-Month"), "3m": (90, "3-Month")}
NEW_DAYS = 7
SEVERITIES = ("S1", "S2", "S3", "S4")


def category(record: dict) -> str | None:
    """Analyzed means the team can start on a fix, so a triaged run that still asks for
    artifacts (a profile, a log) needs info."""
    cat = CATEGORY.get(record["decision"])
    return "needs-info" if cat == "analyzed" and record["asked"] else cat


def decision_label(decision: str | None) -> str:
    """`triaged` reads as `analyzed`, as in the tabs; other decisions lose the underscore."""
    return DECISION_LABEL.get(decision) or (decision or "").replace("_", " ")


def resolution_label(resolution: str | None) -> str | None:
    return resolution.capitalize() if resolution else None


def move_label(move_to: str | None) -> str | None:
    """The component a bug moved to, without the product when that is Core."""
    return move_to.removeprefix("Core :: ") if move_to else None


def close_kind(record: dict) -> str | None:
    """Where a Close / Reassign run sent the bug, as a chart label."""
    if record["resolution"]:
        return resolution_label(record["resolution"])
    if record["move_to"]:
        return f"Moved to {move_label(record['move_to'])}"
    return None


def tags(record: dict) -> list[str]:
    """Tags that hold for the run itself. `again` depends on the run that the page
    picks, so the page adds it."""
    out = []
    if "regression" in record["keywords_add"] or record["regressed_by_add"]:
        out.append("regression")
    if any(ni["role"] != "reporter" for ni in record["needinfo"]):
        out.append("dev needinfo")
    return out


def is_new(filed: str | None, as_of: datetime) -> bool:
    """Filed in the last NEW_DAYS days."""
    return bool(filed) and as_of - datetime.fromisoformat(filed) <= timedelta(days=NEW_DAYS)


def acted(record: dict) -> bool:
    """A run that changed the bug. Failed and preflight-skipped runs changed nothing."""
    return not record["error"] and record["decision"] != "skipped" and bool(record["started_at"])


def period_start(as_of: datetime, key: str) -> str:
    return (as_of - timedelta(days=PERIODS[key][0])).isoformat()


def run_view(record: dict) -> dict:
    keep = (
        "started_at", "severity", "priority", "needinfo", "asked", "dupe_of", "blocks_add",
        "keywords_add", "regressed_by_add", "other_bugs",
    )  # fmt: skip
    return {
        **{k: record[k] for k in keep},
        "category": category(record),
        "decision": decision_label(record["decision"])
        + (
            ", still asks for artifacts"
            if category(record) != CATEGORY.get(record["decision"])
            else ""
        ),
        "resolution": resolution_label(record["resolution"]),
        "move_to": move_label(record["move_to"]),
        "comment_html": render(record["comment"]) if record["comment"] else None,
        "tags": tags(record),
    }


def in_period(records: list[dict], as_of: datetime, key: str) -> list[dict]:
    start = period_start(as_of, key)
    return [r for r in records if acted(r) and r["started_at"] >= start]


def latest_runs(records: list[dict]) -> list[dict]:
    """The newest run of each bug."""
    best: dict[int, dict] = {}
    for r in sorted(records, key=order):
        best[r["bug_id"]] = r
    return list(best.values())


def by_severity(runs: list[dict]) -> dict[str, int]:
    counts = Counter(r["severity"] for r in runs)
    return {s: counts[s] for s in SEVERITIES}


def by_category(runs: list[dict]) -> dict[str, int]:
    counts = Counter(map(category, runs))
    return {c: counts[c] for c in CATEGORIES}


def shown_runs(bug_runs: list[dict]) -> list[dict]:
    """A bug's runs, newest first, as the page shows them: the newest run, then the earlier
    ones only if they and the newest were posted. Dry-run rounds rerun the same bugs as
    tests, so a dry run is never history."""
    newest, earlier = bug_runs[0], bug_runs[1:]
    return [newest, *(r for r in earlier if r["posted"])] if newest["posted"] else [newest]


def bugs(records: list[dict], as_of: datetime) -> list[dict]:
    """Each bug the bot changed, with the runs the page shows. Title and the `new` tag come
    from the newest run."""
    by_bug: dict[int, list[dict]] = {}
    for r in sorted(filter(acted, records), key=order, reverse=True):
        by_bug.setdefault(r["bug_id"], []).append(r)
    return [
        {
            "bug_id": bug_id,
            "title": bug_runs[0]["title"],
            "tags": ["new"] if is_new(bug_runs[0]["filed"], as_of) else [],
            "runs": [run_view(r) for r in shown_runs(bug_runs)],
        }
        for bug_id, bug_runs in by_bug.items()
    ]


def overview(records: list[dict], as_of: datetime) -> dict:
    """Per period: the counts, where closed bugs went, and the severity the bot set. Each
    bug counts once, by its newest run in the period."""
    out = {}
    for key in PERIODS:
        runs = in_period(records, as_of, key)
        latest = latest_runs(runs)
        out[key] = {
            "counts": {"all": len(latest), **by_category(latest)},
            "close_kinds": dict(
                Counter(close_kind(r) for r in latest if category(r) == "close").most_common()
            ),
            "severity": by_severity(latest),
        }
    return out


def team_page(records: list[dict], as_of: datetime) -> dict:
    """Records are one team's. The page holds only the longest period."""
    longest = max(PERIODS, key=lambda k: PERIODS[k][0])
    records = in_period(records, as_of, longest)
    return {
        "as_of": as_of.isoformat(),
        "posted": any(r["posted"] for r in records),
        "categories": [
            {"key": c, "label": CATEGORY_LABEL[c], "color": CATEGORY_COLOR[c], "harm": c == "close"}
            for c in CATEGORIES
        ],
        "risk": list(RISK),
        "periods": [
            {"key": k, "label": label, "days": days, "start": period_start(as_of, k)}
            for k, (days, label) in PERIODS.items()
        ],
        "overview": overview(records, as_of),
        "bugs": bugs(records, as_of),
    }
