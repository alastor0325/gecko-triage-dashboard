"""Command line: ingest dry-run outputs and /triage drafts, then build the site."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from . import bmo, render, stats, store
from .baseline import baseline_entry
from .dryrun import is_public, orphan_bugs, parse_summary, summary_bug_id
from .teams import TEAMS

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs.json"
BASELINE = ROOT / "data" / "baseline.json"
CACHE = ROOT / ".cache" / "bmo"
_RUN_LOG = re.compile(r"run-(\d+)\.log$")


def read_manifest(text: str) -> list[tuple[str, str | None, str]]:
    """Rows of `round<TAB>commit<TAB>dir`; `-` is an unknown commit; `#` starts a comment."""
    rows = []
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            round_, commit, directory = line.split("\t")
            rows.append((round_, None if commit == "-" else commit, directory))
    return rows


def read_round(round_dir: Path) -> list[tuple[Path, dict, int]]:
    """Each run of a round with its bug id. A crashed run has no findings, so its bug is
    the one bug that has a run log but no summary."""
    logged = [
        int(m.group(1)) for p in round_dir.glob("run-*.log") if (m := _RUN_LOG.search(p.name))
    ]
    paths = sorted(round_dir.glob("local-*/summary.json"))
    summaries = [json.loads(p.read_text()) for p in paths]
    orphans = orphan_bugs(logged, summaries)
    runs = []
    for path, summary in zip(paths, summaries, strict=True):
        bug_id = summary_bug_id(summary) or (next(iter(orphans)) if len(orphans) == 1 else None)
        if bug_id is None:
            print(f"skip {path}: no bug id ({len(orphans)} bugs without a summary)")
            continue
        runs.append((path, summary, bug_id))
    return runs


def ingest_dryrun(args) -> None:
    rounds = [
        (r, c, read_round(Path(args.root) / d))
        for r, c, d in read_manifest(Path(args.manifest).read_text())
    ]
    metas = bmo.fetch_meta({bug_id for *_, runs in rounds for _, _, bug_id in runs}, CACHE)
    new = []
    for round_, commit, runs in rounds:
        count = 0
        for path, summary, bug_id in runs:
            meta = metas.get(bug_id)
            if meta is None or not is_public(meta):
                print(f"skip {path}: bug {bug_id} is not public")
                continue
            record = parse_summary(
                summary,
                bug_id=bug_id,
                round_=round_,
                commit=commit,
                run_id=path.parent.name,
                meta=meta,
            )
            if record["team"] is None:
                print(f"skip {path}: bug {bug_id} is in no team's component")
                continue
            new.append(record)
            count += 1
        print(f"{round_}: {count} runs")
    store.save(RUNS, store.merge_records(store.load(RUNS, []), new))


def ingest_baseline(args) -> None:
    out = {}
    for bug_id in sorted({r["bug_id"] for r in store.load(RUNS, [])}):
        draft = store.load(Path(args.dir) / f"bug-{bug_id}.json", None)
        if draft is not None:
            out[str(bug_id)] = baseline_entry(draft)
    store.save(BASELINE, out)
    print(f"baseline: {len(out)} bugs")


def page_clock(records: list[dict], now: datetime) -> datetime:
    """Dry runs are a frozen snapshot, so their clock is the newest run. Posted runs are
    live, so their clock is the build time."""
    if any(r["posted"] for r in records):
        return now
    return max(datetime.fromisoformat(r["started_at"]) for r in records if r["started_at"])


def build(args) -> None:
    records = store.load(RUNS, [])
    baseline = {int(k): v for k, v in store.load(BASELINE, {}).items()}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(render.TEMPLATES / "style.css", out / "style.css")
    team_template = (render.TEMPLATES / "team.html").read_text()
    pages = {}
    for team in TEAMS:
        mine = [r for r in records if r["team"] == team.slug]
        if not mine:
            continue
        pages[team.slug] = page = stats.team_page(mine, baseline, page_clock(mine, datetime.now()))
        (out / team.slug).mkdir(exist_ok=True)
        (out / team.slug / "index.html").write_text(render.team_html(team_template, team, page))
    landing = (render.TEMPLATES / "index.html").read_text()
    (out / "index.html").write_text(render.landing_html(landing, TEAMS, pages))
    print(f"built {out}: {', '.join(pages) or 'no teams'}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="triagedash")
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("ingest-dryrun", help="add the dry-run rounds listed in a manifest")
    p.add_argument("--root", required=True, help="directory the manifest paths are under")
    p.add_argument("manifest")
    p.set_defaults(func=ingest_dryrun)
    p = sub.add_parser("ingest-baseline", help="add /triage drafts for the ingested bugs")
    p.add_argument("dir")
    p.set_defaults(func=ingest_baseline)
    p = sub.add_parser("build", help="write the static site")
    p.add_argument("--out", default="site")
    p.set_defaults(func=build)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
