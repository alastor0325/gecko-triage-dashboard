# Live sources: dry runs, then the pilot, then Hackbot

Status: proposal, not built. The pilot is on hold until Alastor discusses it again.
Facts about hackbot-api are from bugbug `82b12879`. Facts about the pilot are from
`~/firefox-bug-investigation/gecko-triage-hackbot/pilot-plan.md`, which is planned and not
built.

## Principle

The dashboard reports exactly what gecko-triage did, so its source of truth is the run
records: one record for each run the agent made, whatever happened to the run. Bugzilla is
not a source of runs. A search on Bugzilla cannot list the runs that failed, were rejected,
were skipped or changed nothing, and it can miss bugs. Bugzilla only adds details to a
known run: the bug title and component, needinfo names, the comment link, and later the
follow-up signals.

## One record shape, one adapter per source

| Source | Input | Run key | Where it runs |
|---|---|---|---|
| `dryrun` (today) | `~/hackbot/<round>/local-*/summary.json`, listed in `data/rounds.tsv` | `local-<UTC time>-<hex>` | Alastor's Mac |
| `pilot` | `~/hackbot/pilot/log.jsonl`, plus the `summary.json` that each line names | `local-<UTC time>-<hex>` | Alastor's Mac |
| `hackbot` | `GET /runs?agent=gecko-triage`, plus `GET /runs/{id}/actions` | `run_id`, a uuid4 | Mac first, then the GitHub Action |

Each adapter turns its input into the record shape in `triagedash/dryrun.py`. The stats, the
page and the scrubbing do not change. The same runtime writes the local `summary.json` and
`RunDoc.summary` (hackbot-runtime `finalize_run` reads the same file), so the
findings-and-actions part is shared code.

New record fields, the same for every source:

- `source`: `dryrun`, `pilot` or `hackbot`.
- `outcome`: `posted`, `partly posted`, `held`, `rejected`, `shadow`, `skipped`, `failed`
  or `not posted` (dry runs). This replaces the single `posted` flag.
- `posted_at` (UTC), and `applied`: one entry per action with `ok` and the HTTP status. The
  dupe_of bug's meta bug update is its own entry, because it is a separate PUT that can fail
  on its own.
- `comment_count`, for a link to `show_bug.cgi?id=N#cK`. Hackbot does not keep the comment
  id, so its adapter looks up the tagged comment on Bugzilla.
- `agent_version`: the agent commit, or at least the footer rules version.
- `team`, from the run's inputs rather than from today's component. This also holds after a
  bug moves out of the team.

## Keeping what we have

- `data/runs.json` is the dashboard's own archive. It is committed, so git keeps every past
  version. A source can stop (the pilot) or lose data (Hackbot has no retention policy in
  its code), and the records already ingested stay.
- Records are keyed by `(source, run_id)`. Local ids and Hackbot uuids cannot collide.
- Runs are grouped by bug. A bug's history can hold dry runs, pilot runs and Hackbot runs,
  each labelled by source. Dry runs keep today's rule: never history and never `again`.

## Switch steps

1. Pilot: ingest `log.jsonl` daily on the Mac. Every line becomes a record, so skipped,
   failed, rejected and shadow runs are visible too.
2. Stop the pilot, then do a last pilot ingest. The pilot plan already stops the pilot
   before Hackbot starts, so the same bug does not get both on one day.
3. Turn on the Hackbot adapter. It pages back from the newest run until it reaches a run
   it already has, then fetches again the runs that are still running or have pending
   actions, because their state can change after the first read. With no date filter in
   the API, it starts from the switch date.
4. Pilot records stay. The page shows both sources, and the header names the sources it
   holds, so "dry run" stops being the label for everything.

## Open decisions (Alastor's)

1. Failed runs: show them as their own group with the error reason, outside the three
   categories. With agent commit `bcd6e792`, an `analyzed` run that still asks for data
   fails with an error, so today those runs would vanish from the dashboard.
2. Pilot log: one line for every run, not only reviewed ones, plus an `inputs` object in
   the `RunDoc.inputs` shape. gecko-triage proposed both. The dashboard needs both for a
   complete report.
3. Agent version: a small agent change that writes the agent version into findings. Then
   Hackbot runs carry it too. Today they have only the footer rules version.
4. Hackbot read access: there is one shared `X-API-Key`, and it can also apply actions,
   which write to Bugzilla. Interim: run the Hackbot ingest on the Mac and push only the
   scrubbed data, if Alastor accepts the key on his Mac. Later: ask the Hackbot team for a
   read-only key or export, and move the ingest to the GitHub Action.
5. Shadow mode after the switch: the pilot plan has none.

## Never read

`logs/agent.log` and other files under `/runs/{id}/artifacts`. They hold full bug,
attachment and code content. Only `summary` and the action rows are read, and they are
scrubbed as today.
