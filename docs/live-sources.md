# Live sources: from dry runs to real runs

Status: proposal, not built. Facts about hackbot-api are from bugbug `82b12879`
(`services/hackbot-api/app/routers/runs.py`, `schemas.py`, `auth.py`,
`actions_applier.py`, `action_handlers/bugzilla_handler.py`).

## Today

`scripts/ingest-local.sh` reads `~/hackbot/<round>/local-*/summary.json` on Alastor's Mac,
adds public Bugzilla data (title, component, filed date, needinfo names), scrubs it and
writes `data/runs.json`. The Pages workflow only builds the committed data. Nothing reaches
the site unless someone ingests and pushes.

## The question

When gecko-triage runs for real, where does the dashboard read what the bot did?

## Option A: public Bugzilla (recommended for the first live version)

Once a run is posted, everything the team sees is on the bug:

| Dashboard field | Bugzilla source |
|---|---|
| a run, its time | a comment with `comment_tag=gecko-triage`; its `creation_time` |
| the comment, the link | the comment text and its `count` (`show_bug.cgi?id=N#cK`) |
| asked, unread | the footer line `gecko-triage · rules <v> · asked: … · unread: …` |
| S/P, needinfo, blocks, keywords, regressed_by, move, resolution, dupe_of | the bug history entry with the same `when` as the comment, by the bot account |
| category | from those changes plus `asked`, with the same rules as today |
| follow-up signals | later history entries by other accounts (S/P changed, reopened, moved back) |

- Read with no key, from the GitHub Action, on a daily schedule.
- Find bugs with one search on the team's components and `comment_tag=gecko-triage`,
  changed since the last build.
- It shows exactly what reached Bugzilla. A refused update is visibly missing.

Limits:
- No held, failed or skipped runs. These are operator data, not part of the MVP.
- The decision is derived, not read. It needs the footer to stay stable, so the agent
  and this repo must change the footer together.
- If people post manual triage from the same account, history entries must be matched
  to the tagged comment by time.

## Option B: the Hackbot run store

`GET /runs?agent=gecko-triage` (paged by `limit` and `offset`, newest first, no date
filter), then `GET /runs/{id}/actions` for each action's `status`, `result` and
`applied_at`. `RunDoc.summary` is the same summary.json that is read today, so the
record mapping barely changes. `run_id` (a uuid4) becomes the record key.

Gaps:
- **Key:** one shared `X-API-Key` that can also start runs and apply actions, which write
  to Bugzilla. It must not go in a repo secret without the Hackbot team's agreement. Ask
  them for a read-only key or a read-only export.
- **Missing fields:** no comment id (Option A can fill it), no approver, and no start or
  finish time in the API (use `created_at` and `updated_at`).
- **Retention:** no policy in the code.
- **Logs:** never read `logs/agent.log` through `/artifacts`. It holds full bug,
  attachment and code content. Read `summary` and `actions` only, scrubbed as today.

Its value is what Bugzilla cannot show: held runs waiting for approval, failed runs, and
what the bot would have done.

## Plan

1. Pilot: ingest `pilot/log.jsonl` with its summary.json files. The log has `posted_at`,
   `applied` and `comment_id`, and sets `posted`.
2. Live, first version: Option A in the GitHub Action, daily. No key, no Mac.
3. Later, if held or failed runs matter: Option B with a read-only key from the Hackbot
   team, merged on `run_id` and on the bug plus the comment time.

Each source is one adapter that produces the record shape in `triagedash/dryrun.py`. The
stats, the page and the scrubbing stay as they are.
