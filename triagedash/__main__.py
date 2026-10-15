"""Command line: ingest the agent's runs, then build the site."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from . import bmo, hackbot, render, stats, store
from .summary import is_public, orphan_bugs, parse_summary, requestees, summary_bug_id
from .teams import TEAMS

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs.json"
PASSES = ROOT / "data" / "passes.json"
CACHE = ROOT / ".cache" / "bmo"
_RUN_LOG = re.compile(r"run-(\d+)\.log$")


def read_manifest(text: str) -> list[tuple[str, str]]:
    """Rows of `round<TAB>dir`; `#` starts a comment."""
    rows = []
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            round_, directory = line.split("\t")
            rows.append((round_, directory))
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


_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def day_folders(pilot: Path) -> list[str]:
    """The official daily runs: one `<YYYY-MM-DD>` folder per day, oldest first."""
    if not pilot.is_dir():
        return []
    return [p.name for p in sorted(pilot.iterdir()) if p.is_dir() and _DAY.match(p.name)]


def rounds_to_ingest(root: Path, manifest: str) -> list[tuple[str, Path, str]]:
    """(round, folder, source) for every daily folder under `root/pilot`, then every test
    round in the manifest."""
    daily = [(d, root / "pilot" / d, "daily") for d in day_folders(root / "pilot")]
    tests = [(r, root / d, "test") for r, d in read_manifest(manifest)]
    return daily + tests


def ingest(args) -> None:
    """Adds every run of the daily folders and the manifest rounds to data/runs.json."""
    manifest = Path(args.manifest).read_text() if args.manifest else ""
    rounds = [
        (r, source, read_round(folder))
        for r, folder, source in rounds_to_ingest(Path(args.root), manifest)
    ]
    hackbot_dir = Path(args.root) / hackbot.DIR
    docs = list(hackbot.stored(hackbot_dir).values())
    local = [(s, bug_id) for *_, runs in rounds for _, s, bug_id in runs]
    remote = [(hackbot.summary_of(d), hackbot.bug_of(d)) for d in docs]
    metas = bmo.fetch_meta({bug_id for _, bug_id in local + remote}, CACHE)
    users = bmo.fetch_users(
        {e for s, bug_id in local + remote for e in requestees(s, bug_id)}, CACHE
    )
    log = store.load_jsonl(Path(args.root) / "pilot" / "log.jsonl")
    teams = store.log_teams(log)
    new = []
    for round_, source, runs in rounds:
        count = 0
        for path, summary, bug_id in runs:
            meta = metas.get(bug_id)
            if meta is None or not is_public(meta):
                print(f"skip {path}: bug {bug_id} is not public")
                continue
            run_id = path.parent.name
            record = parse_summary(
                summary,
                bug_id=bug_id,
                run_id=run_id,
                meta=meta,
                users=users,
                source=source,
                team=store.local_team(teams, run_id),
            )
            new.append(store.unreviewed(record) if source == "daily" else record)
            count += 1
        print(f"{round_} ({source}): {count} runs")
    if docs:
        remote_records = hackbot.records(docs, metas, users, hackbot.load_reviews(hackbot_dir))
        new += remote_records
        print(f"hackbot: {len(remote_records)} runs")
    merged = store.shown(store.merge_records(store.load(RUNS, []), new))
    records = store.apply_log(merged, log)
    print(f"pilot log: {sum(r['posted'] for r in records)} posted runs")
    store.save(RUNS, records)
    pilot_passes = store.load_jsonl(Path(args.root) / "pilot" / "passes.jsonl")
    passes = store.merge_passes(store.load(PASSES, []), pilot_passes)
    print(f"passes: {len(passes)}")
    store.save(PASSES, passes)


def fetch_hackbot(args) -> None:
    """Downloads the gecko-triage runs from hackbot-api. Off until a key exists."""
    try:
        key = hackbot.load_key()
    except hackbot.KeyFileError as e:
        raise SystemExit(str(e)) from e
    if not key:
        print("off: no key (Keychain item 'hackbot-api' or ~/.config/hackbot/key, mode 600)")
        return
    base = os.environ.get("HACKBOT_API_URL", hackbot.DEFAULT_URL)
    n = hackbot.fetch(hackbot.http_getter(base, key), Path(args.out), hackbot.now_utc())
    print(f"hackbot: {n} runs downloaded to {args.out}")


def review(args) -> None:
    """Records that a Hackbot run was rejected, in the review log next to the downloads."""
    hackbot.reject(Path(args.out), args.run_id, args.reject, hackbot.now_utc())
    print(f"rejected {args.run_id}: do not apply it in Hackbot")


def page_clock(records: list[dict], now: datetime) -> datetime:
    """Test rounds are a frozen snapshot, so their clock is the newest run. History runs
    (posted or daily) are live, so their clock is the build time, and the periods and the
    `new` tag age out if the runs stop."""
    if any(map(stats.is_history, records)):
        return now
    return max(datetime.fromisoformat(r["started_at"]) for r in records if r["started_at"])


def build(args) -> None:
    records = store.load(RUNS, [])
    passes = store.load(PASSES, [])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ("review-stats.css", "favicon.svg"):
        shutil.copy(render.TEMPLATES / name, out / name)
    team_template = (render.TEMPLATES / "team.html").read_text()
    pages = {}
    for team in TEAMS:
        mine = [r for r in records if r["team"] == team.slug]
        if not mine:
            continue
        clock = page_clock(mine, datetime.now(UTC))
        team_passes = [p for p in passes if p["team"] == team.slug]
        pages[team.slug] = page = stats.team_page(mine, clock, team_passes)
        (out / team.slug).mkdir(exist_ok=True)
        (out / team.slug / "index.html").write_text(render.team_html(team_template, team, page))
    landing = (render.TEMPLATES / "index.html").read_text()
    (out / "index.html").write_text(render.landing_html(landing, TEAMS, pages))
    print(f"built {out}: {', '.join(pages) or 'no teams'}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="triagedash")
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("ingest", help="add the daily runs and the manifest's test rounds")
    p.add_argument("--root", required=True, help="the hackbot folder: pilot/<day>/ and rounds")
    p.add_argument("--manifest", help="test rounds: round<TAB>directory under --root")
    p.set_defaults(func=ingest)
    p = sub.add_parser("fetch-hackbot", help="download gecko-triage runs from hackbot-api")
    p.add_argument("--out", default=str(hackbot.default_out()))
    p.set_defaults(func=fetch_hackbot)
    p = sub.add_parser("review", help="record that a Hackbot run was rejected")
    p.add_argument("run_id")
    p.add_argument("--reject", required=True, metavar="REASON")
    p.add_argument("--out", default=str(hackbot.default_out()))
    p.set_defaults(func=review)
    p = sub.add_parser("build", help="write the static site")
    p.add_argument("--out", default="site")
    p.set_defaults(func=build)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
