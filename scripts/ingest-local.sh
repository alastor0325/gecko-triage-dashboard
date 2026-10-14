#!/bin/sh
# Ingests every dry-run round in data/rounds.tsv, then the /triage drafts. Needs
# ~/hackbot and ~/firefox-triage/pending, so it runs on Alastor's Mac, not in CI.
set -eu
uv run python -m triagedash ingest-dryrun --root "${HACKBOT_DIR:-$HOME/hackbot}" data/rounds.tsv
uv run python -m triagedash ingest-baseline "${TRIAGE_PENDING:-$HOME/firefox-triage/pending}"
