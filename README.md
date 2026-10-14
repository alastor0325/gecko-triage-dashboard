# gecko-triage-dashboard

A static, per-team dashboard over the output of the
[gecko-triage](https://github.com/alastor0325/bugbug/tree/gecko-triage/agent/agents/gecko-triage)
Hackbot agent. It has the same style as
[firefox-review-stats](https://alastor0325.github.io/firefox-review-stats/): a landing
page lists each team, and each team has its own page.

**Live**: <https://alastor0325.github.io/gecko-triage-dashboard/>

## What it shows

The page answers one question for the team: **what did the bot change on our bugs, and
does any of it look wrong?** One page per team, with fixed controls, so it does not grow
with the number of rounds:

- **Tabs**: Closed, Moved, S/P set, Needs info and All, in order of harm if the bot is
  wrong, each with its count. Left/Right change the tab.
- **When**: the last 7 days (default), the last 30 days, all time, or one round.
- **Search**: bug id, title or tag. `/` puts the cursor in it.
- **List (short view)**: one row per bug, with its newest run in the chosen period, the
  main action, tags and title. The riskiest changes come first. Up/Down or j/k step
  through it.
- **Card (full view)**: S/P badges, every change the bot made, the bot's short summary,
  the earlier runs on the bug (collapsed), and a link to Bugzilla.

Tags: `new` (filed in the last 7 days), `regression` (the bot added the keyword or
`regressed_by`), `dev needinfo` (the bot asked someone other than the reporter, and it
never closes those) and `again` (the bot came back to the bug; posted runs only, because
dry-run rounds rerun the same bugs as tests).

Failed runs and runs that the preflight skipped changed nothing, so the page leaves them
out. Cost, run health and accuracy are not part of this MVP.

The layout follows the local triage dashboard (firefox-triage-dashboard), and the favicon
is its own.
The style is a copy of firefox-review-stats: `templates/review-stats.css` is copied
verbatim from its team template, and `templates/index.html` from its landing page. Change
those files there first, then copy them again.

## Data

`data/runs.json` has one record per agent run, and it is committed. `data/rounds.tsv`
lists each dry-run round and its directory. The site is public, so the records keep no
email address: a needinfo becomes a role (`reporter`, `assignee` or `other`), and every
string is scrubbed of emails and `:nick` mentions. Restricted bugs are never ingested. A
run's team comes from its bug's component. Times are stored in UTC.

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
