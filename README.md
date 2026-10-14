# gecko-triage-dashboard

A static, per-team dashboard over the output of the
[gecko-triage](https://github.com/alastor0325/bugbug/tree/gecko-triage/agent/agents/gecko-triage)
Hackbot agent. It has the same style as
[firefox-review-stats](https://alastor0325.github.io/firefox-review-stats/): a landing
page lists each team, and each team has its own page.

**Live**: <https://alastor0325.github.io/gecko-triage-dashboard/>

## Views

Each team page has five views and a period switch (1W, 1M, 3M, All):

- **Overview**: bugs triaged, S/P set, needinfo asked, closed and moved; decisions;
  severity; who the needinfo went to; bugs triaged per week.
- **Bugs**: the latest run of each bug, with its decision and every change it records.
  Filter by decision and component, or search.
- **Waiting**: bugs with a needinfo from the bot.
- **Run health**: runs, failed runs, cost and turns; unread artifacts; each round.
- **Accuracy (beta)**: in the dry-run phase, agreement with the local /triage draft of
  the same bug. Later, changes that people make after the bot.

Left/Right change the view, Shift+Left/Right the period. The URL hash keeps the state,
for example `#overview/1m`.

## Data

`data/runs.json` has one record per agent run, and `data/baseline.json` has the /triage
reference for each bug. Both are committed. `data/rounds.tsv` lists each dry-run round,
the agent commit it ran on, and its directory. The site is public, so the records keep
no email address: a needinfo becomes a role (`reporter`, `assignee` or `other`), and
every string is scrubbed of emails and `:nick` mentions. Restricted bugs are never
ingested. A run's team comes from its bug's component.

v1 reads the local dry runs. Bugzilla (`comment_tag=gecko-triage`) comes next.

## Commands

```
uv sync
./scripts/ingest-local.sh                 # every round in data/rounds.tsv, then the /triage drafts
uv run python -m triagedash ingest-dryrun --root ~/hackbot data/rounds.tsv
uv run python -m triagedash ingest-baseline ~/firefox-triage/pending
uv run python -m triagedash build --out site
uv run pytest tests/unit/
```

To add a round, add a line to `data/rounds.tsv` and run `ingest-local.sh`. `ingest-dryrun`
reads `local-*/summary.json` in each directory and the bugs' public Bugzilla fields, in
one request (cached in `.cache/bmo/`). A re-ingest replaces a run with the same id.
`HACKBOT_DIR` and `TRIAGE_PENDING` change the input paths of `ingest-local.sh`.

## Adding a team

Add a `Team` to `TEAMS` in `triagedash/teams.py`, with the components from the agent's
`teams/<team>/team.toml`. Runs on bugs in those components then go to that team.

## Publishing

`.github/workflows/pages.yml` runs lint and tests, builds the site, and deploys it to
GitHub Pages on every push to `main`. A daily run comes with the Bugzilla source,
because the dry-run data only changes on push.
