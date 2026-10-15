"""Turns one gecko-triage run's `summary.json` into a dashboard record.

A record holds no email address, because the site is public: a needinfo requestee becomes
a role and their public Bugzilla name and nick, and every string is scrubbed in
`parse_summary`. The page builds the `Name (:nick)` label.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from .teams import team_for

_RUN_ID = re.compile(r"local-(\d{8}-\d{6})-[0-9a-f]+$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_MENTION = re.compile(r"(?<![\w/:]):[A-Za-z][\w-]*\b")


def run_started_at(run_id: str) -> str | None:
    """`local-20261014-174025-eb0234` -> `2026-10-14T17:40:25+00:00`. hackbot-runtime
    names a local run by its start time in UTC."""
    m = _RUN_ID.search(run_id)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=UTC).isoformat()


def scrub(value):
    """Removes emails and `:nick` mentions from every string, at any depth."""
    if isinstance(value, str):
        return _MENTION.sub(":[person]", EMAIL.sub("[email]", value))
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


# hackbot-runtime's COMMENT_FOOTER_SEPARATOR (hackbot_runtime.actions.bugzilla); keep in
# step. The trailer after it holds the feedback sentence, which the agent rewrites, and on
# older runs the agent's `gecko-triage · rules …` line, so it is found by these markers.
_TRAILER_SEPARATOR = "\n\n---\n\n"
_TRAILER_MARKERS = ("feedback on this comment", "triage · rules ")


def strip_footer(comment: str | None) -> str | None:
    """Drops the trailer that ends every bot comment."""
    head, sep, tail = (comment or "").rpartition(_TRAILER_SEPARATOR)
    return head if sep and any(m in tail for m in _TRAILER_MARKERS) else comment


def summary_bug_id(summary: dict) -> int | None:
    return (summary.get("findings") or {}).get("bug_id")


def orphan_bugs(logged: list[int], summaries: list[dict]) -> set[int]:
    """Bugs in a round that have a run log but no summary with findings."""
    return set(logged) - {summary_bug_id(s) for s in summaries}


_BRACKETS = re.compile(r"\s*[\[(][^\])]*[\])]")


def clean_real_name(real_name: str | None) -> str | None:
    """`Pat Doe [:pdoe] (PTO)` -> `Pat Doe`: Bugzilla real names often carry the nick and
    notes in brackets. A name that is only the nick is dropped."""
    name = _BRACKETS.sub("", real_name or "").strip()
    return name if name and not name.startswith(":") else None


def update_actions(summary: dict, bug_id: int) -> tuple[dict, list[dict]]:
    """The run's changes to its own bug, merged, and its updates of other bugs."""
    own: dict = {}
    other: list[dict] = []
    for action in summary.get("actions") or []:
        params = action.get("params") or {}
        if action.get("type") != "bugzilla.update_bug":
            continue
        if params.get("bug_id") == bug_id:
            own.update(params.get("changes") or {})
        else:
            other.append(params)
    return own, other


def needinfo_flags(changes: dict) -> list[dict]:
    return [f for f in changes.get("flags") or [] if f.get("name") == "needinfo"]


def requestees(summary: dict, bug_id: int) -> set[str]:
    """Every needinfo requestee the run sets on its own bug, so their public names can be
    looked up in one pass."""
    own, _ = update_actions(summary, bug_id)
    return {f["requestee"] for f in needinfo_flags(own) if f.get("requestee")}


def needinfo_entry(requestee: str | None, meta: dict, users: dict[str, dict]) -> dict:
    """Who a needinfo asks: their role on the bug, public real name and bare nick."""
    user = users.get(requestee) or {}
    return {
        "role": needinfo_role(requestee, meta),
        "name": clean_real_name(user.get("real_name")),
        "nick": user.get("nick"),
    }


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


def parse_summary(
    summary: dict,
    *,
    bug_id: int,
    run_id: str,
    meta: dict,
    users: dict[str, dict],
    source: str,
) -> dict:
    """`meta` is the bug's public Bugzilla data: creator, assigned_to, product, component,
    summary, groups, creation_time. `users` maps a requestee email to its public Bugzilla
    name and nick. `bug_id` comes from the caller, since a crashed run has no findings.
    `source` is `daily` for an official daily run and `test` for a test round."""
    findings = summary.get("findings") or {}
    own, other = update_actions(summary, bug_id)
    other_bugs = [
        {"bug_id": p.get("bug_id"), "blocks_add": _added(p.get("changes") or {}, "blocks")}
        for p in other
    ]
    comments = [
        (a.get("params") or {}).get("text")
        for a in summary.get("actions") or []
        if a.get("type") == "bugzilla.add_comment"
    ]
    comment = comments[-1] if comments else None
    record = {
        "posted": False,
        "source": source,
        "run_id": run_id,
        "started_at": run_started_at(run_id),
        "bug_id": bug_id,
        "title": meta.get("summary"),
        "filed": meta.get("creation_time"),
        "team": team_for(meta.get("product"), meta.get("component")),
        "error": summary.get("status") != "ok" or bool(summary.get("error")),
        "decision": findings.get("decision"),
        "comment": strip_footer(comment),
        "severity": own.get("severity"),
        "priority": own.get("priority"),
        "asked": list(findings.get("asked") or []),
        "agent_version": findings.get("agent_version"),
        "needinfo": [needinfo_entry(f.get("requestee"), meta, users) for f in needinfo_flags(own)],
        "blocks_add": _added(own, "blocks"),
        "keywords_add": _added(own, "keywords"),
        "regressed_by_add": _added(own, "regressed_by"),
        "move_to": _move_target(own, meta),
        "resolution": own.get("resolution"),
        "dupe_of": own.get("dupe_of"),
        "other_bugs": other_bugs,
    }
    return scrub(record)


def is_public(meta: dict) -> bool:
    return not meta.get("groups")
