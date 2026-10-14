#!/bin/sh
# Ingests every dry-run round in data/rounds.tsv. Needs ~/hackbot, so it runs on
# Alastor's Mac, not in CI.
set -eu
uv run python -m triagedash ingest-dryrun --root "${HACKBOT_DIR:-$HOME/hackbot}" data/rounds.tsv
