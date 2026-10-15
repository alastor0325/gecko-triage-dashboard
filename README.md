# gecko-triage-dashboard

A static, per-team dashboard over the output of the
[gecko-triage](https://github.com/alastor0325/bugbug/tree/gecko-triage/agent/agents/gecko-triage)
Hackbot agent. It has the same style as
[firefox-review-stats](https://alastor0325.github.io/firefox-review-stats/): a landing
page lists each team, and each team has its own page.

**Live**: <https://alastor0325.github.io/gecko-triage-dashboard/>

## What it shows

The page answers one question for the team: **what did the bot do on our bugs, and does
any of it look wrong?** Each team page has two views and a period toggle, as in
firefox-review-stats: Overview and Bugs, over 1-Week (default), 1-Month or 3-Month. Left/Right
change the view, Shift+Left/Right the period, and the URL hash keeps both
(`#overview/1w`, `#bugs/1m/close/2080127`).

The categories are those of the local triage dashboard, from the bot's decision. Each bug
is in exactly one: **Analyzed** (`analyzed`, or `triaged` in earlier runs: the team can
start on a fix), **Needs info** (`needs_info`; `watching`, a return that waits on a stale
needinfo to a developer; and any `triaged` run that still asks for artifacts such as a
profile or a log) and **Close / Reassign** (`duplicate`, `invalid`, `wrong_component`,
`incomplete`, `stalled`). S/P can be set in Analyzed and in Needs info.

- **Overview**: the count of bugs handled and of each category (a click on a tile opens
  the Bugs view on that category); bugs handled per day,
  stacked by category; where the Close / Reassign bugs went (resolution or new
  component); and the severity the bot set.
- **Bugs**: category filters with counts, and a search by id, title or tag (`/` puts the
  cursor in it). A list (short view) shows one row per bug, with its newest run in the
  period, riskiest first: Close / Reassign, then Analyzed, then Needs info. Up/Down or j/k
  step through it. Each row shows only the bug number, its category (in the All tab
  only) and the `regression` and `new` tags. A card (full view) shows all tags and the
  bot's timeline on the bug: the newest run with every change and the whole comment the
  bot posted, then the earlier posted runs, folded. Dry-run rounds rerun the same bugs as
  tests, so the page data keeps only each bug's newest dry run. Every bug number links to Bugzilla.

Each bug counts once in a period, by its newest run. Tags: `new` (filed in the last 7
days), `regression` (the bot added the keyword or `regressed_by`), `dev needinfo` (the bot
asked someone other than the reporter, and it never closes those) and `again` (the bot
came back to the bug; posted runs only, because dry-run rounds rerun the same bugs as
tests).

The page holds only the last 3 months. Failed runs, runs that the preflight skipped and
runs that ended before they decided changed nothing, so the page leaves them out. Cost,
run health and accuracy are not part of this MVP.

The layout of the Bugs view follows the local triage dashboard (firefox-triage-dashboard),
and the favicon is its own.
The style is firefox-review-stats': `templates/review-stats.css` is copied verbatim from
its team template, so change it there first and copy it again. `templates/index.html` is
its landing page with this dashboard's text.

## Data

`data/runs.json` has one record per agent run, and it is committed. `data/rounds.tsv`
lists each dry-run round and its directory (the round name is used in the ingest log
only). The site is public, so the records keep no email address: a needinfo becomes the
person's role (`reporter`, `assignee` or `other`) and their public Bugzilla name and nick,
looked up at ingest, and every string is scrubbed of emails and `:nick` mentions. The card
shows who each needinfo asks. Restricted bugs are never ingested. A run's team comes from
its bug's component. Times are stored in UTC, and the page shows them in the viewer's time
zone; the per-day chart counts by the viewer's local day.

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
