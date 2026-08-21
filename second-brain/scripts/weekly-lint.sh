#!/usr/bin/env bash
# WEEKLY: keep the graph clean. Runs the deterministic linter first, then hands
# the report to a cheap-model pass to fix/flag. Routine work.
# Cron, e.g.:  0 3 * * 1  /path/to/second-brain/scripts/weekly-lint.sh
set -euo pipefail
dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vault="$(cd "$dir/.." && pwd)"

report="$(python3 "$dir/lint.py" "$vault")"
echo "$report"

exec "$dir/_run.sh" prompts/lint.md SB_CHEAP_MODEL claude-haiku-4-5-20251001 \
  "Deterministic lint report follows. Act on it.

$report"
