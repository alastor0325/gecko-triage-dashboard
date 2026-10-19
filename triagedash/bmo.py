"""Reads public bug data from Bugzilla, anonymously, with a disk cache."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

from . import store

FIELDS = "id,creator,assigned_to,product,component,summary,groups,creation_time"
BASE = "https://bugzilla.mozilla.org/rest/bug"
USERS = "https://bugzilla.mozilla.org/rest/user"


def fetch_meta(bug_ids: set[int], cache_dir: Path) -> dict[int, dict]:
    """The public fields of each bug, in one request for the bugs not cached yet.

    A restricted or missing bug is absent from the result; the cache keeps it as `{}`."""
    missing = sorted(b for b in bug_ids if not (cache_dir / f"{b}.json").exists())
    if missing:
        found = {b["id"]: b for b in get_bugs(set(missing), FIELDS)}
        for b in missing:
            store.save(cache_dir / f"{b}.json", found.get(b, {}))
    metas = {b: store.load(cache_dir / f"{b}.json", {}) for b in bug_ids}
    return {b: m for b, m in metas.items() if m}


BUG_CHUNK = 100  # bug ids per request, to keep the URL short


def get_bugs(bug_ids: set[int], fields: str) -> list[dict]:
    """The bugs an anonymous reader can see, with `fields`. A restricted or missing bug is
    left out: Bugzilla answers the same for both."""
    ids = sorted(bug_ids)
    out = []
    for i in range(0, len(ids), BUG_CHUNK):
        chunk = ",".join(map(str, ids[i : i + BUG_CHUNK]))
        url = f"{BASE}?id={chunk}&include_fields={fields}&permissive=1"
        with urllib.request.urlopen(url, timeout=60) as resp:
            out += json.load(resp).get("bugs") or []
    return out


def fetch_visible(bug_ids: set[int]) -> set[int]:
    """The bugs an anonymous reader can see. Not cached: a bug can become restricted at
    any time, and the answer decides what the public page shows."""
    return {b["id"] for b in get_bugs(bug_ids, "id")}


USER_CHUNK = 100  # names per request, to keep the URL short


def fetch_users(emails: set[str], cache_dir: Path) -> dict[str, dict]:
    """The public Bugzilla real name and nick of each account, fetching only the accounts
    not cached yet. An unknown account maps to empty fields."""
    path = cache_dir / "users.json"
    cache = store.load(path, {})
    missing = sorted(e for e in emails if e not in cache)
    for i in range(0, len(missing), USER_CHUNK):
        chunk = missing[i : i + USER_CHUNK]
        query = "&".join(f"names={urllib.parse.quote(e)}" for e in chunk)
        with urllib.request.urlopen(
            f"{USERS}?{query}&include_fields=name,real_name,nick", timeout=60
        ) as resp:
            found = {u["name"]: u for u in json.load(resp).get("users") or []}
        for e in chunk:
            cache[e] = {
                "real_name": found.get(e, {}).get("real_name"),
                "nick": found.get(e, {}).get("nick"),
            }
    if missing:
        store.save(path, cache)
    return {e: cache[e] for e in emails}
