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
needinfo to a developer; `stalled`, which keeps the bug open for volunteers; and any
`triaged` run that still asks for artifacts such as a profile or a log) and **Close /
Reassign** (`duplicate`, `invalid`, `wrong_component`, `incomplete`). S/P can be set in
Analyzed and in Needs info.

- **Overview**: the count of bugs handled and of each category (a click on a tile opens
  the Bugs view on that category); bugs handled per day, stacked by category; where the
  Close / Reassign bugs went (resolution or new component); the severity the bot set; and
  the issue types (a click on a bar opens the Bugs view on that type). The type is
  `findings.issue_type`, one value from the team's list; runs made before the agent saved
  it take it from `~/hackbot/pilot/issue-types.jsonl`, else `unknown`. The note of an
  `other` type stays in the data, unshown, to find values the list is missing.
- **Bugs**: category filters with counts, and a search by id, title or tag (`/` puts the
  cursor in it). A list (short view) shows one row per bug, with its newest run in the
  period, newest first, under a header for each day ("Today", "Yesterday", then the date)
  with its bug count. Up/Down or j/k step through it. Each row shows only the bug number,
  its category (in the All and Close / Reassign tabs) and the `regression` and `new` tags.
  A card (full view) shows all tags and the bot's
  timeline on the bug: every run (posted or daily), newest first and none folded, each with
  its day and time, every change and the whole comment. Test rounds rerun the same bugs
  as tests, so the page data keeps only each bug's newest test run. Every bug number links
  to Bugzilla, and each run names the agent version that made it
  (`findings.agent_version`; older runs show no version).
- **Calendar** (media only): one round of the weekly triage rotation, the current week
  and the weeks before it, one per engineer. Each open Analyzed or Needs info bug that
  nobody is assigned to sits in the week of its newest run, in two groups: bugs the
  engineer can start work on (under a header per severity on Bugzilla now, most severe first), and bugs to
  check if they want to be involved. A bug closed on Bugzilla now is left out. A click on
  a week opens its bugs, and a click on a bug opens its card in place.

A Close / Reassign bug's category reads `Closed` when the run set a resolution, else
`Reassigned` when it moved the bug.

Each bug counts once in a period, by its newest run. Tags: `new` (filed in the last 7
days), `regression` (the bot added the keyword or `regressed_by`), `dev needinfo` (the bot
asked someone other than the reporter, and it never closes those) and `again` (the bot
came back to the bug; posted runs only, because dry-run rounds rerun the same bugs as
tests).

The page holds only the last 3 months. Failed runs, runs that the preflight or the pilot
log skipped, runs that ended before they decided, and runs that posted no comment and
changed no field (such as `watching` runs) changed nothing, so the page leaves them out. Cost,
run health and accuracy are not part of this MVP.

The layout of the Bugs view follows the local triage dashboard (firefox-triage-dashboard),
and the favicon is its own.
The style is firefox-review-stats': `templates/review-stats.css` is copied verbatim from
its team template, so change it there first and copy it again. `templates/index.html` is
its landing page with this dashboard's text.

## Data

`data/runs.json` has one record per agent run, and it is committed, so git keeps every
day. There are two kinds of run:

- **Official daily runs** (`source: daily`): one folder per day under
  `~/hackbot/pilot/<YYYY-MM-DD>/`, read on their own. A bug can appear on many days, or
  several times on one day. Every run is kept, the newest sets the bug's state, and the
  earlier ones show in the card as history.
- **Test rounds** (`source: test`): the rounds listed in `data/rounds.tsv`, none today.
  They rerun the same bugs as tests, so only each bug's newest test run is shown.

`data/rotation.json` holds the rotation weeks (first name, start and end) from the public
`js/media.ics` of mozilla/media-triage, which syncs its Google Calendar every day. Swaps
and cancelled weeks are applied, and emails are never read out of the file.
`data/bug-state.json` says whether each bug is open now, whether someone is assigned, and
its severity now, from an anonymous Bugzilla read; the assignee is never kept.
`triagedash refresh` writes both; the deploy runs it every day and on each push.

`data/fix-tags.json` holds the proposed whiteboard fix tags (`[gecko-triage:easy-fix]`,
`[gecko-triage:gfb-candidate]`) from the newest `~/hackbot/pilot/fix-tags-*.jsonl`: only the
bug and its tags. The page shows the strongest one as a solid tag, "easy fix" or "gfb"
("good first bug" on the card), until the refresh finds it on the bug's whiteboard.

`data/passes.json` has one line per daily selection pass (team, UTC time, bugs selected),
from `~/hackbot/pilot/passes.jsonl`. With it, "Bugs handled per day" marks a day with no
bar as `0` (the bot ran and found no bug) or `×` (no run recorded). Today, and every day
from the first Hackbot run on, get no mark: a Hackbot pass that selects no bug leaves no
trace.

The site is public, so the records keep no email address: a needinfo becomes the person's
role (`reporter`, `assignee` or `other`) and their public Bugzilla name and nick, looked
up at ingest, and every string is scrubbed of emails and `:nick` mentions. The card shows
who each needinfo asks. Restricted bugs are never ingested. The dashboard is for the media
team only, so it shows only runs made for team `media`: `inputs.team` in the pilot log or
in the Hackbot run, and `media` for a local run with no log line yet. A run made for no
team, or for another team, is not shown. Times are stored
in UTC (a run folder is named by its UTC start time), and the page shows them in the
viewer's time zone; the per-day chart counts by the viewer's local day.

`docs/live-sources.md` plans the move to posted runs and to Hackbot.

## Commands

```
uv sync
./scripts/ingest-local.sh                 # every daily folder, then data/rounds.tsv
uv run python -m triagedash ingest --root ~/hackbot --manifest data/rounds.tsv
uv run python -m triagedash build --out site
uv run pytest tests/unit/
```

`ingest` reads `local-*/summary.json` in each daily folder and test round, and the
bugs' public Bugzilla fields, in one request (cached in `.cache/bmo/`). A re-ingest
replaces a run with the same id, so running it twice is safe. `HACKBOT_DIR` changes the
input path of `ingest-local.sh`.

## Hackbot runs

Once gecko-triage runs on Hackbot, its runs show next to the local ones, with
`source: hackbot`. Run the download on the Mac before `ingest-local.sh`:

```
uv run python -m triagedash fetch-hackbot              # off until a key exists
uv run python -m triagedash review <run_id> --reject "reason"
```

- `fetch-hackbot` reads the key from the Keychain item `hackbot-api`, else from
  `~/.config/hackbot/key` (mode 600 only), and `HACKBOT_API_URL` (default
  `https://hackbot-api.moz.tools`). It saves each gecko-triage run and its action rows in
  `~/hackbot/hackbot-runs/<UTC day>/<run_id>.json`, without the requester's email. It
  never fetches `/artifacts`, so logs with full bug text never reach the dashboard.
- hackbot-api has no reject state, so `review --reject` writes the rejection to
  `~/hackbot/hackbot-runs/reviews.jsonl`.
- A Hackbot run's outcome is `failed`, `rejected`, `posted`, `partly posted`,
  `apply failed` or `awaiting review`. A rejected run whose actions are still pending
  gets a red notice in the card: applying it later would post a second comment.

## Adding a team

Add a `Team` to `TEAMS` in `triagedash/teams.py`, with the components from the agent's
`teams/<team>/team.toml` (the landing page lists them). Runs whose input names that team
then go to its page. Local runs are all `LOCAL_TEAM` (media) today.

## Publishing

`.github/workflows/pages.yml` runs lint and tests, builds the site, and deploys it to
GitHub Pages on every push to `main`. A daily run comes with the Bugzilla source,
because the dry-run data only changes on push.
