"""Groups records into the calendar weeks one team page shows. Pure: no I/O."""

from __future__ import annotations

from datetime import date, datetime, timedelta

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


def acted(record: dict) -> bool:
    """A run that changed the bug. Failed and preflight-skipped runs changed nothing."""
    return not record["error"] and record["decision"] != "skipped" and bool(record["started_at"])


def week_of(started_at: str) -> tuple[str, date]:
    """The ISO week key and its Monday."""
    day = datetime.fromisoformat(started_at).date()
    year, week, weekday = day.isocalendar()
    return f"{year}-W{week:02d}", day - timedelta(days=weekday - 1)


def latest_runs(records: list[dict]) -> list[dict]:
    """The newest run of each bug."""
    best: dict[int, dict] = {}
    for r in sorted(records, key=lambda r: (when(r), r["run_id"])):
        best[r["bug_id"]] = r
    return list(best.values())


def risk_rank(row: dict) -> int:
    """The index of the row's riskiest category; a comment-only row ranks last."""
    return CATEGORIES.index(row["categories"][0]) if row["categories"] else len(CATEGORIES)


def by_risk(rows: list[dict]) -> list[dict]:
    """Riskiest first, so the triager can stop when time runs out; then newest first."""
    newest = sorted(rows, key=lambda r: r["started_at"], reverse=True)
    return sorted(newest, key=risk_rank)


def row(record: dict) -> dict:
    keep = (
        "bug_id", "title", "summary", "started_at", "severity", "priority",
        "needinfo", "resolution", "dupe_of", "move_to", "blocks_add", "keywords_add",
        "regressed_by_add", "other_bugs",
    )  # fmt: skip
    return {**{k: record[k] for k in keep}, "categories": categories(record)}


def weeks(records: list[dict]) -> list[dict]:
    """Per calendar week, newest first: the latest run of each bug the bot changed."""
    by_week: dict[str, tuple[date, list[dict]]] = {}
    for r in filter(acted, records):
        key, monday = week_of(r["started_at"])
        by_week.setdefault(key, (monday, []))[1].append(r)
    out = []
    for key, (monday, runs) in sorted(by_week.items(), reverse=True):
        rows = by_risk([row(r) for r in latest_runs(runs)])
        out.append(
            {
                "key": key,
                "start": monday.isoformat(),
                "end": (monday + timedelta(days=6)).isoformat(),
                "rows": rows,
                "counts": {
                    "all": len(rows),
                    **{c: sum(c in r["categories"] for r in rows) for c in CATEGORIES},
                },
            }
        )
    return out


def team_page(records: list[dict], as_of: datetime) -> dict:
    """Records are one team's."""
    return {
        "as_of": as_of.isoformat(),
        "posted": any(r["posted"] for r in records),
        "categories": list(CATEGORIES),
        "weeks": weeks(records),
    }
