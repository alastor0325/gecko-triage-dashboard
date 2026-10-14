"""Turns one gecko-triage dry-run `summary.json` into a dashboard record.

A record holds no email address: needinfo requestees become roles, and every string is
scrubbed in `parse_summary`, because the site is public.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, tzinfo

from .teams import team_for

_RUN_ID = re.compile(r"local-(\d{8}-\d{6})-[0-9a-f]+$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_MENTION = re.compile(r"(?<![\w/]):[A-Za-z][\w-]*\b")


def run_started_at(run_id: str, host_tz: tzinfo | None = None) -> str | None:
    """`local-20261014-174025-eb0234` -> the start time in UTC. The name holds the time
    of the host that ran the agent; `host_tz` defaults to this machine's zone, since
    ingest runs on that host."""
    m = _RUN_ID.search(run_id)
    if not m:
        return None
    local = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    if host_tz is not None:
        local = local.replace(tzinfo=host_tz)
    return local.astimezone(UTC).isoformat()


def scrub(value):
    """Removes emails and `:nick` mentions from a string, or from each string in a list."""
    if isinstance(value, str):
        return _MENTION.sub(":[person]", EMAIL.sub("[email]", value))
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def summary_bug_id(summary: dict) -> int | None:
    return (summary.get("findings") or {}).get("bug_id")


def orphan_bugs(logged: list[int], summaries: list[dict]) -> set[int]:
    """Bugs in a round that have a run log but no summary with findings."""
    return set(logged) - {summary_bug_id(s) for s in summaries}


def needinfo_role(requestee: str | None, meta: dict) -> str:
    if not requestee:
        return "unknown"
    if requestee == meta.get("creator"):
        return "reporter"
    if requestee == meta.get("assigned_to"):
        return "assignee"
    return "other"


def _added(changes: dict, field: str) -> list:
    value = changes.get(field)
    return list(value.get("add", [])) if isinstance(value, dict) else []


def _move_target(changes: dict, meta: dict) -> str | None:
    if not (changes.get("product") or changes.get("component")):
        return None
    product = changes.get("product") or meta.get("product")
    return f"{product} :: {changes.get('component') or meta.get('component')}"


def parse_summary(summary: dict, *, bug_id: int, run_id: str, meta: dict) -> dict:
    """`meta` is the bug's public Bugzilla data: creator, assigned_to, product, component,
    summary, groups. `bug_id` comes from the caller, since a crashed run has no findings."""
    findings = summary.get("findings") or {}
    own: dict = {}
    other_bugs: list[dict] = []
    for action in summary.get("actions") or []:
        params = action.get("params") or {}
        if action.get("type") != "bugzilla.update_bug":
            continue
        changes = params.get("changes") or {}
        if params.get("bug_id") == bug_id:
            own.update(changes)
        else:
            other_bugs.append(
                {"bug_id": params.get("bug_id"), "blocks_add": _added(changes, "blocks")}
            )
    flags = [f for f in own.get("flags") or [] if f.get("name") == "needinfo"]
    record = {
        "posted": False,
        "run_id": run_id,
        "started_at": run_started_at(run_id),
        "bug_id": bug_id,
        "title": meta.get("summary"),
        "team": team_for(meta.get("product"), meta.get("component")),
        "error": summary.get("status") != "ok" or bool(summary.get("error")),
        "decision": findings.get("decision"),
        "summary": findings.get("summary"),
        "severity": own.get("severity"),
        "priority": own.get("priority"),
        "needinfo": [needinfo_role(f.get("requestee"), meta) for f in flags],
        "blocks_add": _added(own, "blocks"),
        "keywords_add": _added(own, "keywords"),
        "regressed_by_add": _added(own, "regressed_by"),
        "move_to": _move_target(own, meta),
        "resolution": own.get("resolution"),
        "dupe_of": own.get("dupe_of"),
        "other_bugs": other_bugs,
    }
    return {k: scrub(v) for k, v in record.items()}


def is_public(meta: dict) -> bool:
    return not meta.get("groups")
