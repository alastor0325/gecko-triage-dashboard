#!/bin/sh
# Ingests the official daily runs ($HACKBOT_DIR/pilot/<YYYY-MM-DD>/) and the test rounds in
# data/rounds.tsv. Needs ~/hackbot, so it runs on Alastor's Mac.
set -eu
uv run python -m triagedash ingest --root "${HACKBOT_DIR:-$HOME/hackbot}" --manifest data/rounds.tsv
uv run python -m triagedash refresh
