"""Hackbot runs: download them from hackbot-api, and turn them into dashboard records.

The download runs on Alastor's Mac only. The X-API-Key comes from the macOS Keychain or a
mode-600 file and is never written anywhere. Only the run and its action rows are fetched:
never `/artifacts`, which holds logs/agent.log with full bug text and tool output.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from . import store
from .summary import is_public, parse_summary

DEFAULT_URL = "https://hackbot-api.moz.tools"
KEYCHAIN_SERVICE = "hackbot-api"
KEY_FILE = Path.home() / ".config" / "hackbot" / "key"
AGENT = "gecko-triage"
DIR = "hackbot-runs"
REVIEWS = "reviews.jsonl"
PAGE = 100
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FINISHED = ("succeeded", "failed", "timed_out")
# Fields of a RunDoc that the dashboard never needs; requested_by is an email.
DROPPED = ("requested_by", "artifacts")


class KeyFileError(Exception):
    pass


def key_from_file(path: Path) -> str | None:
    """The key in `path`, or None if there is no file. A file that others can read is
    refused rather than used."""
    if not path.exists():
        return None
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise KeyFileError(f"{path} must be mode 600")
    return path.read_text().strip() or None


def key_from_keychain(service: str = KEYCHAIN_SERVICE) -> str | None:
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:  # not macOS
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def load_key() -> str | None:
    return key_from_keychain() or key_from_file(KEY_FILE)


def settled(run: dict, actions: list[dict]) -> bool:
    """A run whose stored state cannot change any more: finished, and with no action that
    is still pending. A succeeded run with no rows yet is not settled, because a person can
    still apply it."""
    if run.get("status") not in FINISHED:
        return False
    if run.get("status") != "succeeded":
        return True
    return bool(actions) and all(a.get("status") != "pending" for a in actions)


def slim(run: dict) -> dict:
    return {k: v for k, v in run.items() if k not in DROPPED}


def stored(out_dir: Path) -> dict[str, dict]:
    """Every downloaded run, by run id."""
    paths = (p for p in out_dir.glob("*/*.json") if DAY.match(p.parent.name))
    return {p.stem: json.loads(p.read_text()) for p in paths}


def is_settled(doc: dict) -> bool:
    return settled(doc["run"], doc["actions"])


def needs_fetch(run_id: str, known: dict[str, dict]) -> bool:
    return run_id not in known or not is_settled(known[run_id])


def day_of(run: dict) -> str:
    return datetime.fromisoformat(run["created_at"]).astimezone(UTC).date().isoformat()


Getter = Callable[[str], object]


def http_getter(base: str, key: str) -> Getter:
    def get(path: str):
        req = urllib.request.Request(f"{base}{path}", headers={"X-API-Key": key})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)

    return get


def fetch(get: Getter, out_dir: Path, now: str) -> int:
    """Downloads every new or unsettled gecko-triage run into `out_dir/<day>/<run_id>.json`.
    Paging stops at the first page with nothing to fetch. Returns how many runs were
    written."""
    known = stored(out_dir)
    ids: dict[str, None] = {}
    offset = 0
    while True:
        page = get(f"/runs?agent={AGENT}&limit={PAGE}&offset={offset}")
        fresh = [r["run_id"] for r in page if needs_fetch(r["run_id"], known)]
        ids.update(dict.fromkeys(fresh))
        if len(page) < PAGE or not fresh:
            break
        offset += PAGE
    ids.update(dict.fromkeys(rid for rid in known if needs_fetch(rid, known)))
    for rid in ids:
        run = slim(get(f"/runs/{rid}"))
        actions = get(f"/runs/{rid}/actions")
        path = out_dir / day_of(run) / f"{rid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"run": run, "actions": actions, "fetched_at": now}, indent=1))
    return len(ids)


def latest_reviews(lines: list[dict]) -> dict[str, dict]:
    """The newest review line for each run id."""
    out: dict[str, dict] = {}
    for line in sorted(lines, key=lambda line: line.get("at") or ""):
        out[line["run_id"]] = line
    return out


def load_reviews(out_dir: Path) -> dict[str, dict]:
    return latest_reviews(store.load_jsonl(out_dir / REVIEWS))


def reject(out_dir: Path, run_id: str, reason: str, now: str) -> None:
    """Records in the review log that a person rejected the run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / REVIEWS).open("a") as f:
        line = {"run_id": run_id, "review": "rejected", "at": now, "reason": reason}
        f.write(json.dumps(line) + "\n")


def outcome(run: dict, actions: list[dict], review: dict | None) -> dict:
    """What happened to a Hackbot run, in the same words as a local run's log outcome.
    hackbot-api has no reject state, so `rejected` comes only from the review log, and is
    kept apart from what reached Bugzilla."""
    status = Counter(a.get("status") for a in actions)
    posted_at = max((a["applied_at"] for a in actions if a.get("applied_at")), default=None)
    rejected = bool(review and review.get("review") == "rejected")
    if run.get("status") in ("failed", "timed_out"):
        result = "failed"
    elif status["applied"]:
        result = "posted" if not (status["failed"] or status["pending"]) else "partly posted"
    elif rejected:
        result = "rejected"
    elif status["failed"] and not status["pending"]:
        result = "apply failed"
    else:
        result = "awaiting review"
    return {
        "outcome": result,
        "rejected": rejected,
        "posted": bool(status["applied"]),
        "posted_at": posted_at,
        "pending_actions": status["pending"],
    }


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def default_out() -> Path:
    return Path(os.environ.get("HACKBOT_DIR", Path.home() / "hackbot")) / DIR


def to_record(doc: dict, meta: dict, users: dict[str, dict], review: dict | None) -> dict:
    """A downloaded run as a dashboard record: the summary parsed and scrubbed as for local
    runs, plus its outcome from the action rows and the review log."""
    run = doc["run"]
    record = parse_summary(
        summary_of(doc),
        bug_id=bug_of(doc),
        run_id=run["run_id"],
        meta=meta,
        users=users,
        source="hackbot",
        team=team_of(doc),
        started_at=run["created_at"],
    )
    result = outcome(run, doc["actions"], review)
    return {**record, **result, "error": record["error"] or result["outcome"] == "failed"}


def bug_of(doc: dict) -> int:
    return doc["run"]["inputs"]["bug_id"]


def team_of(doc: dict) -> str | None:
    return doc["run"]["inputs"].get("team")


def summary_of(doc: dict) -> dict:
    return doc["run"].get("summary") or {}


def records(docs: list[dict], metas: dict, users: dict, reviews: dict) -> list[dict]:
    """The records of every downloaded run on a public bug. `store.shown` then keeps the
    runs made for a shown team."""
    out = []
    for doc in docs:
        meta = metas.get(bug_of(doc))
        if meta is None or not is_public(meta):
            continue
        out.append(to_record(doc, meta, users, reviews.get(doc["run"]["run_id"])))
    return out
