#!/bin/sh
# Downloads the gecko-triage runs from hackbot-api (off when no key is set), then ingests the
# official daily runs ($HACKBOT_DIR/pilot/<YYYY-MM-DD>/), the Hackbot runs
# ($HACKBOT_DIR/hackbot-runs/) and the test rounds in data/rounds.tsv.
set -eu
root="${HACKBOT_DIR:-$HOME/hackbot}"
uv run python -m triagedash fetch-hackbot --out "$root/hackbot-runs" \
  || echo "hackbot: download failed; the ingest goes on with the runs already stored"
uv run python -m triagedash ingest --root "$root" --manifest data/rounds.tsv
uv run python -m triagedash refresh
