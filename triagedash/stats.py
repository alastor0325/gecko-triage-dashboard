"""Aggregates records into the numbers one team page shows. Pure: no I/O."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from statistics import median

from .baseline import agent_category
from .store import when

# key: (days or None for all time, button label, window name)
PERIODS = {
    "1w": (7, "1W", "1-week"),
    "1m": (30, "1M", "1-month"),
    "3m": (90, "3M", "3-month"),
    "all": (None, "All", "all-time"),
}


def _ok(record: dict) -> bool:
    return not record["error"]


def latest_runs(records: list[dict]) -> list[dict]:
    """The newest successful run of each bug, or its newest run if every run failed,
    newest first."""
    best: dict[int, dict] = {}
    for r in sorted(records, key=lambda r: (_ok(r), when(r), r["run_id"])):
        best[r["bug_id"]] = r
    return sorted(best.values(), key=when, reverse=True)


def in_window(records: list[dict], as_of: datetime, days: int | None) -> list[dict]:
    if days is None:
        return list(records)
    start = (as_of - timedelta(days=days)).isoformat()
    return [r for r in records if when(r) >= start]


def iso_week(started_at: str) -> str:
    year, week, _ = datetime.fromisoformat(started_at).isocalendar()
    return f"{year}-W{week:02d}"


def overview(bugs: list[dict], runs: list[dict]) -> dict:
    acted = [b for b in bugs if _ok(b) and b["decision"] != "skipped"]
    weekly: dict[str, set[int]] = {}
    for r in runs:
        if _ok(r) and r["started_at"] and r["decision"] != "skipped":
            weekly.setdefault(iso_week(r["started_at"]), set()).add(r["bug_id"])
    return {
        "tiles": {
            "triaged": len(acted),
            "sp_set": sum(1 for b in acted if b["severity"] or b["priority"]),
            "needinfo": sum(1 for b in acted if b["needinfo"]),
            "closed": sum(1 for b in acted if b["resolution"]),
            "moved": sum(1 for b in acted if b["move_to"]),
        },
        "decisions": dict(Counter(b["decision"] for b in bugs if _ok(b)).most_common()),
        "severity": dict(sorted(Counter(b["severity"] for b in acted if b["severity"]).items())),
        "needinfo_roles": dict(
            Counter(role for b in acted for role in b["needinfo"]).most_common()
        ),
        "weekly": {week: len(ids) for week, ids in sorted(weekly.items())},
    }


def waiting(bugs: list[dict], as_of: datetime) -> list[dict]:
    """Bugs with a needinfo from the bot, longest wait first."""
    rows = [
        {
            "run_id": b["run_id"],
            "days": (as_of - datetime.fromisoformat(b["started_at"])).days
            if b["started_at"]
            else None,
        }
        for b in bugs
        if _ok(b) and b["needinfo"]
    ]
    return sorted(rows, key=lambda r: r["days"] or 0, reverse=True)


def health(runs: list[dict]) -> dict:
    costs = [r["cost_usd"] for r in runs if r["cost_usd"] is not None]
    turns = [r["turns"] for r in runs if r["turns"] is not None]
    rounds: dict[str, dict] = {}
    for r in runs:
        entry = rounds.setdefault(
            r["round"], {"commit": r["commit"], "runs": 0, "errors": 0, "cost_usd": 0.0}
        )
        entry["runs"] += 1
        entry["errors"] += not _ok(r)
        entry["cost_usd"] += r["cost_usd"] or 0
    for entry in rounds.values():
        entry["cost_usd"] = round(entry["cost_usd"], 2)
    return {
        "runs": len(runs),
        "errors": sum(1 for r in runs if not _ok(r)),
        "cost_total": round(sum(costs), 2),
        "cost_median": round(median(costs), 2) if costs else None,
        "turns_median": median(turns) if turns else None,
        "unread": dict(Counter(u for r in runs if _ok(r) for u in r["unread"]).most_common()),
        "skipped": sum(1 for r in runs if r["decision"] == "skipped"),
        "rounds": rounds,
    }


def field_diffs(record: dict, ref: dict) -> list[str]:
    diffs = [
        f"{field}: {record[field]} vs {ref[field]}"
        for field in ("severity", "priority", "resolution", "dupe_of")
        if record[field] != ref[field]
    ]
    if len(record["needinfo"]) != ref["needinfo_count"]:
        diffs.append(f"needinfo: {len(record['needinfo'])} vs {ref['needinfo_count']}")
    return diffs


def agreement(runs: list[dict], baseline: dict[int, dict]) -> dict:
    """Agreement with /triage: per bug on the latest run, and per round."""
    compared = [r for r in runs if _ok(r) and r["bug_id"] in baseline]
    same = {
        r["run_id"]: agent_category(r["decision"]) == baseline[r["bug_id"]]["category"]
        for r in compared
    }
    rounds: dict[str, dict] = {}
    for r in compared:
        entry = rounds.setdefault(r["round"], {"runs": 0, "same": 0})
        entry["runs"] += 1
        entry["same"] += same[r["run_id"]]
    bugs = [
        {
            "run_id": b["run_id"],
            "agent": agent_category(b["decision"]),
            "triage": baseline[b["bug_id"]]["category"],
            "same": same[b["run_id"]],
            "diffs": field_diffs(b, baseline[b["bug_id"]]),
        }
        for b in latest_runs(compared)
    ]
    return {"bugs": bugs, "rounds": rounds}


def team_page(records: list[dict], baseline: dict[int, dict], as_of: datetime) -> dict:
    """Records are one team's. Each run a period shows is stored once, in `runs`."""
    ordered = sorted(records, key=lambda r: (when(r), r["run_id"]))
    periods = {}
    shown: set[str] = set()
    for key, (days, label, name) in PERIODS.items():
        runs = in_window(ordered, as_of, days)
        bugs = latest_runs(runs)
        shown.update(b["run_id"] for b in bugs)
        periods[key] = period = {
            "label": label,
            "name": name,
            "bugs": [b["run_id"] for b in bugs],
            "overview": overview(bugs, runs),
            "waiting": waiting(bugs, as_of),
            "health": health(runs),
            "agreement": agreement(runs, baseline),
        }
        shown.update(b["run_id"] for b in period["agreement"]["bugs"])
    return {
        "as_of": as_of.isoformat(),
        "posted": any(r["posted"] for r in records),
        "runs": {r["run_id"]: r for r in ordered if r["run_id"] in shown},
        "periods": periods,
    }
