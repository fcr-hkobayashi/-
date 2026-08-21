#!/usr/bin/env bash
# WEEKLY: cross-vault synthesis. The ONE pass that earns the premium model.
# Writes synthesis/YYYY-MM-DD-weekly.md.
# Cron, e.g.:  0 4 * * 1  /path/to/second-brain/scripts/weekly-synthesis.sh
set -euo pipefail
dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$dir/_run.sh" prompts/synthesis.md SB_BIG_MODEL claude-opus-4-8 "$@"
