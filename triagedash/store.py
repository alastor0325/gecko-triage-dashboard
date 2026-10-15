"""The committed data file `data/runs.json`."""

from __future__ import annotations

import json
from pathlib import Path

from .teams import LOCAL_TEAM, is_shown


def when(record: dict) -> str:
    return record["started_at"] or ""


def order(record: dict) -> tuple[str, str]:
    """Oldest first; the run id breaks ties."""
    return when(record), record["run_id"]


def merge_records(existing: list[dict], new: list[dict]) -> list[dict]:
    """Upsert by run id, so a re-ingest replaces a run instead of adding it twice."""
    by_id = {r["run_id"]: r for r in existing}
    by_id.update({r["run_id"]: r for r in new})
    return sorted(by_id.values(), key=order)


def merge_passes(existing: list[dict], new: list[dict]) -> list[dict]:
    """The daily selection passes, one per team and time, oldest first. Only the team, the
    time and the count are kept."""
    keep = ("team", "at", "selected")
    by_key = {(p["team"], p["at"]): {k: p[k] for k in keep} for p in existing + new}
    return sorted(by_key.values(), key=lambda p: (p["at"], p["team"]))


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    """One JSON object per line; blank lines are skipped. A missing file is empty."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def log_teams(log: list[dict]) -> dict[str, str | None]:
    """The team each logged run was made for, by run id."""
    return {line["run_id"]: (line.get("inputs") or {}).get("team") for line in log}


def shown(records: list[dict]) -> list[dict]:
    """The records the dashboard shows: the runs made for a team of TEAMS. Applied to the
    whole archive, so a run stored under an older rule is dropped too."""
    return [r for r in records if is_shown(r["team"])]


def local_team(teams: dict[str, str | None], run_id: str) -> str | None:
    """The team a local run was made for: its log line's, else LOCAL_TEAM. A run that waits
    for review may have no log line yet."""
    return teams.get(run_id, LOCAL_TEAM)


def apply_log(records: list[dict], log: list[dict]) -> list[dict]:
    """Marks the runs that the pilot log lists with what happened when they were reviewed.
    A posted run whose writes all succeeded is `posted`, else `partly posted`. Other
    reviews (rejected, skipped, shadow) are kept as the outcome. The log's bot account is
    never copied."""
    by_run = {line["run_id"]: line for line in log}
    out = []
    for r in records:
        line = by_run.get(r["run_id"])
        if line is None:
            out.append(r)
        elif line["review"] != "posted":
            rejected = line["review"] == "rejected"
            out.append({**r, "posted": False, "rejected": rejected, "outcome": line["review"]})
        else:
            ok = all(a.get("ok") for a in line.get("applied") or [])
            out.append(
                {
                    **r,
                    "posted": True,
                    "outcome": "posted" if ok else "partly posted",
                    "posted_at": line.get("posted_at"),
                    "comment_count": line.get("comment_count"),
                }
            )
    return out
