# gecko-triage-dashboard

A static, per-team dashboard over the output of the
[gecko-triage](https://github.com/alastor0325/bugbug/tree/gecko-triage/agent/agents/gecko-triage)
Hackbot agent. It has the same style as
[firefox-review-stats](https://alastor0325.github.io/firefox-review-stats/): a landing
page lists each team, and each team has its own page.

**Live**: <https://alastor0325.github.io/gecko-triage-dashboard/>

## What it shows

The page answers one question for the team's weekly triage: **what did the bot change on
our bugs this week, and is any of it wrong?**

- **Week tabs**: one calendar week per tab, newest first. Left/Right change the week, and
  the URL hash keeps it (`#2026-W42`).
- **Tiles**: all bugs the bot changed, then closed, moved, S/P set and asked for info, in
  order of harm if the bot is wrong. A click on a tile filters the table, and a second click
  clears the filter.
- **Table**: one row for each bug, with the latest run of that week. The riskiest changes
  come first. Each row links to the bug and lists every change.

Failed runs and runs that the preflight skipped changed nothing, so the page leaves them
out. Cost, run health and accuracy are not part of this MVP.

The style is a copy of firefox-review-stats: `templates/review-stats.css` is copied
verbatim from its team template, and `templates/index.html` from its landing page. Change
those files there first, then copy them again.

## Data

`data/runs.json` has one record per agent run, and it is committed. `data/rounds.tsv`
lists each dry-run round and its directory. The site is public, so the records keep no
email address: a needinfo becomes a role (`reporter`, `assignee` or `other`), and every
string is scrubbed of emails and `:nick` mentions. Restricted bugs are never ingested. A
run's team comes from its bug's component. Times are stored in UTC, and a week runs from
Monday to Sunday in UTC.

v1 reads the local dry runs. Bugzilla (`comment_tag=gecko-triage`) comes next.

## Commands

```
uv sync
./scripts/ingest-local.sh                 # every round in data/rounds.tsv
uv run python -m triagedash ingest-dryrun --root ~/hackbot data/rounds.tsv
uv run python -m triagedash build --out site
uv run pytest tests/unit/
```

To add a round, add a line to `data/rounds.tsv` and run `ingest-local.sh`. `ingest-dryrun`
reads `local-*/summary.json` in each directory and the bugs' public Bugzilla fields, in
one request (cached in `.cache/bmo/`). A re-ingest replaces a run with the same id.
`HACKBOT_DIR` changes the input path of `ingest-local.sh`.

## Adding a team

Add a `Team` to `TEAMS` in `triagedash/teams.py`, with the components from the agent's
`teams/<team>/team.toml`. Runs on bugs in those components then go to that team.

## Publishing

`.github/workflows/pages.yml` runs lint and tests, builds the site, and deploys it to
GitHub Pages on every push to `main`. A daily run comes with the Bugzilla source,
because the dry-run data only changes on push.
