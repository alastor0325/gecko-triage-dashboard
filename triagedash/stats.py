"""Shapes one team's records into the page data. Pure: no I/O.

The page shows, per bug, its newest run and the earlier runs that are history (posted, or
official daily runs). Every
date the page shows, including the per-day chart, is in the viewer's time zone, so the
page buckets runs into days itself."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from .markdown import render
from .store import AWAITING_REVIEW, order

# The agent's decision, grouped as the local triage dashboard groups its drafts.
CATEGORY = {
    # `triaged` is the agent's old name for `analyzed`; earlier runs on disk still use it.
    "triaged": "analyzed",
    "analyzed": "analyzed",
    "needs_info": "needs-info",
    # A returning run that waits on a stale needinfo to a developer; not ready for work.
    "watching": "needs-info",
    # A comment for volunteers and the `stalled` keyword: the bug stays open, waiting.
    "stalled": "needs-info",
    **dict.fromkeys(("duplicate", "invalid", "wrong_component", "incomplete"), "close"),
}
# Tab order, as in the triage dashboard, with each tab's label and chart color. The colors
# are COLOR_NAVY, COLOR_MUSTARD and COLOR_RED of the review-stats editorial palette.
CATEGORIES = ("analyzed", "needs-info", "close")
CATEGORY_LABEL = {"analyzed": "Analyzed", "needs-info": "Needs info", "close": "Close / Reassign"}
CATEGORY_COLOR = {"analyzed": "#1B3B6F", "needs-info": "#C89B3C", "close": "#FF0039"}
DECISION_LABEL = {"triaged": "analyzed"}
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


def close_action(record: dict) -> str | None:
    """What a Close / Reassign run did, in the same order as `close_kind`: `Closed` when it
    set a resolution, else `Reassigned` when it moved the bug."""
    if record["resolution"]:
        return "Closed"
    if record["move_to"]:
        return "Reassigned"
    return None


def close_kind(record: dict) -> str | None:
    """Where a Close / Reassign run sent the bug, as a chart label."""
    if record["resolution"]:
        return resolution_label(record["resolution"])
    if record["move_to"]:
        return f"Reassigned to {move_label(record['move_to'])}"
    return None


# Outcomes that need a look. `posted` and `awaiting review` are the normal path, so they
# get no tag; the run line in the card still says them.
PROBLEM_OUTCOMES = ("partly posted", "apply failed")


def outcome_tags(record: dict) -> list[str]:
    """What went wrong with the run: rejected by a person, or not all of it reached
    Bugzilla."""
    out = ["rejected"] if record["rejected"] else []
    if record["outcome"] in PROBLEM_OUTCOMES:
        out.append(record["outcome"])
    return out


def warning(record: dict) -> str | None:
    """`do not apply`: a rejected Hackbot run whose actions are still pending; applying them
    later would post a second comment. `rejected but posted`: it was applied anyway."""
    if not record["rejected"]:
        return None
    if record["posted"]:
        return "rejected but posted"
    return "do not apply" if record["pending_actions"] else None


def tags(record: dict) -> list[str]:
    """Tags that hold for the run itself. `again` depends on the run that the page
    picks, so the page adds it."""
    out = outcome_tags(record)
    if "regression" in record["keywords_add"] or record["regressed_by_add"]:
        out.append("regression")
    if any(ni["role"] != "reporter" for ni in record["needinfo"]):
        out.append("dev needinfo")
    return out


def is_new(filed: str | None, as_of: datetime) -> bool:
    """Filed in the last NEW_DAYS days."""
    return bool(filed) and as_of - datetime.fromisoformat(filed) <= timedelta(days=NEW_DAYS)


# What a run can do on Bugzilla: its comment and every field change.
EFFECTS = (
    "comment", "severity", "priority", "needinfo", "blocks_add", "keywords_add",
    "regressed_by_add", "move_to", "resolution", "dupe_of", "other_bugs",
)  # fmt: skip


def changed_nothing(record: dict) -> bool:
    """A run with no comment and no field change, such as a `watching` run."""
    return not any(record[k] for k in EFFECTS)


def acted(record: dict) -> bool:
    """A run whose decision has a category and that does something on Bugzilla. Failed
    runs, preflight skips, runs that ended before they decided, runs the pilot log marks
    skipped, and runs that change nothing are left out."""
    return (
        not record["error"]
        and record["decision"] in CATEGORY
        and record["outcome"] != "skipped"
        and not changed_nothing(record)
        and bool(record["started_at"])
    )


def period_start(as_of: datetime, key: str) -> str:
    """The start of a period: midnight UTC of the first of its calendar days, today being
    the last. The page counts the same days in the viewer's time zone."""
    first = as_of.astimezone(UTC).date() - timedelta(days=PERIODS[key][0] - 1)
    return datetime.combine(first, datetime.min.time(), UTC).isoformat()


# The page cuts periods by the viewer's local day, which can start up to a day before the
# UTC one, so its data reaches one day further back.
DATA_MARGIN = timedelta(days=1)


def run_view(record: dict) -> dict:
    keep = (
        "started_at", "source", "posted", "pending_actions", "outcome", "posted_at",
        "comment_count", "severity", "priority", "needinfo", "asked", "dupe_of", "blocks_add",
        "keywords_add", "regressed_by_add", "other_bugs", "agent_version",
    )  # fmt: skip
    cat = category(record)
    action = close_action(record) if cat == "close" else None
    reclassified = cat != CATEGORY.get(record["decision"])
    return {
        **{k: record[k] for k in keep},
        "category": cat,
        "decision": decision_label(record["decision"])
        + (", still asks for artifacts" if reclassified else ""),
        "resolution": resolution_label(record["resolution"]),
        "move_to": move_label(record["move_to"]),
        "comment_html": render(record["comment"]) if record["comment"] else None,
        "tags": tags(record),
        "warning": warning(record),
        "issue_type": issue_type(record),
        "close_kind": close_kind(record) if cat == "close" else None,
        "close_action": action,
        "label_kind": action.lower() if action else cat,
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


def is_history(run: dict) -> bool:
    """A run that is part of the bug's history: posted, or an official run (local daily or
    Hackbot). Test rounds rerun the same bugs, so their runs are never history."""
    return run["posted"] or run["source"] in ("daily", "hackbot")


def shown_runs(bug_runs: list[dict]) -> list[dict]:
    """A bug's runs, newest first, as the page shows them: the newest run, then the earlier
    real runs if the newest is real too."""
    newest, earlier = bug_runs[0], bug_runs[1:]
    return [newest, *filter(is_history, earlier)] if is_history(newest) else [newest]


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
            "filed": (filed := bug_runs[0]["filed"]),
            "first_run": bug_runs[-1]["started_at"],
            "tags": ["new"] if is_new(filed, as_of) else [],
            "runs": [run_view(r) for r in shown_runs(bug_runs)],
        }
        for bug_id, bug_runs in by_bug.items()
    ]


def issue_type(record: dict) -> str:
    return record["issue_type"] or "unknown"


def overview(records: list[dict], as_of: datetime) -> dict:
    """Per period: the counts, where closed bugs went, the severity the bot set and the issue
    types. Each bug counts once, by its newest run in the period."""
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
            "issue_types": dict(Counter(map(issue_type, latest)).most_common()),
        }
    return out


def ran_at(records: list[dict], passes: list[dict], start: str) -> list[str]:
    """When the bot is known to have run since `start`, oldest first: each daily pass, also
    one that selected no bug, and each official run. A test round is not a daily pass."""
    times = [p["at"] for p in passes] + [
        r["started_at"] for r in records if r["source"] in ("daily", "hackbot") and r["started_at"]
    ]
    return sorted(t for t in set(times) if t >= start)


def known_until(records: list[dict], as_of: datetime) -> str:
    """The end of the days on which a missing run is known to mean "no run": the page clock,
    or the first Hackbot run, because a Hackbot pass that selects no bug leaves no trace."""
    hackbot = [r["started_at"] for r in records if r["source"] == "hackbot"]
    return min([as_of.isoformat(), *hackbot])


def team_page(records: list[dict], as_of: datetime, passes: list[dict] = ()) -> dict:
    """Records and passes are one team's. The page holds only the longest period."""
    longest = max(PERIODS, key=lambda k: PERIODS[k][0])
    start = (datetime.fromisoformat(period_start(as_of, longest)) - DATA_MARGIN).isoformat()
    ran = ran_at(records, passes, start)
    until = known_until(records, as_of)
    records = [r for r in records if acted(r) and r["started_at"] >= start]
    return {
        "as_of": as_of.isoformat(),
        "ran_at": ran,
        "known_until": until,
        "severities": list(SEVERITIES),
        "first_run": min([*ran, *(r["started_at"] for r in records)], default=None),
        "posted": sum(r["posted"] for r in records),
        "categories": [
            {"key": c, "label": CATEGORY_LABEL[c], "color": CATEGORY_COLOR[c]} for c in CATEGORIES
        ],
        "periods": [
            {"key": k, "label": label, "days": days} for k, (days, label) in PERIODS.items()
        ],
        # Only the landing page reads these; the team page counts in the viewer's days.
        "week_counts": overview(records, as_of)["1w"]["counts"],
        "bugs": (page_bugs := bugs(records, as_of)),
        "awaiting": sum(b["runs"][0]["outcome"] == AWAITING_REVIEW for b in page_bugs),
    }
