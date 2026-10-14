"""Reads public bug data from Bugzilla, anonymously, with a disk cache."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from . import store

FIELDS = "id,creator,assigned_to,product,component,summary,groups"
BASE = "https://bugzilla.mozilla.org/rest/bug"


def fetch_meta(bug_ids: set[int], cache_dir: Path) -> dict[int, dict]:
    """The public fields of each bug, in one request for the bugs not cached yet.

    A restricted or missing bug is absent from the result; the cache keeps it as `{}`."""
    missing = sorted(b for b in bug_ids if not (cache_dir / f"{b}.json").exists())
    if missing:
        url = f"{BASE}?id={','.join(map(str, missing))}&include_fields={FIELDS}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            found = {b["id"]: b for b in json.load(resp).get("bugs") or []}
        for b in missing:
            store.save(cache_dir / f"{b}.json", found.get(b, {}))
    metas = {b: store.load(cache_dir / f"{b}.json", {}) for b in bug_ids}
    return {b: m for b, m in metas.items() if m}
