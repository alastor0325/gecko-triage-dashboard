"""The committed data file `data/runs.json`."""

from __future__ import annotations

import json
from pathlib import Path


def when(record: dict) -> str:
    return record["started_at"] or ""


def merge_records(existing: list[dict], new: list[dict]) -> list[dict]:
    """Upsert by run id, so a re-ingest replaces a run instead of adding it twice."""
    by_id = {r["run_id"]: r for r in existing}
    by_id.update({r["run_id"]: r for r in new})
    return sorted(by_id.values(), key=lambda r: (when(r), r["run_id"]))


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n")
