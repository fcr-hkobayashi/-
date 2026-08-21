#!/usr/bin/env bash
# NIGHTLY: compile new raw/ material into the wiki. Cheap model, routine work.
# Wire to cron, e.g.:  0 2 * * *  /path/to/second-brain/scripts/nightly-compile.sh
set -euo pipefail
dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$dir/_run.sh" prompts/compile.md SB_CHEAP_MODEL claude-haiku-4-5-20251001 "$@"
