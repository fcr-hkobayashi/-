#!/usr/bin/env bash
# SESSION-END HOOK: fires on its own when a Claude Code session ends, mines the
# transcript for durable signal, and writes it into the vault.
#
# Wire it in your Claude Code settings (see scripts/settings.hook.json) as a
# SessionEnd hook. It reads the hook's JSON payload from stdin.
#
# Recursion guard: the mining pass itself is a Claude Code session, so we set
# SB_IN_HOOK=1 and bail if it's already set, so the hook never triggers itself.
set -euo pipefail

if [ "${SB_IN_HOOK:-0}" = "1" ]; then
  exit 0
fi

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Hook payload arrives on stdin as JSON; pull the transcript path if present.
payload="$(cat || true)"
transcript=""
if command -v python3 >/dev/null 2>&1; then
  transcript="$(printf '%s' "$payload" | python3 -c \
    'import json,sys;
try:
    print(json.load(sys.stdin).get("transcript_path",""))
except Exception:
    print("")' 2>/dev/null || true)"
fi

context="A Claude Code session just ended."
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  context="$context Its transcript is at: $transcript
Read that transcript to mine what happened."
fi

# Run the miner in the background so ending a session stays instant.
SB_IN_HOOK=1 nohup "$dir/_run.sh" prompts/session-end.md SB_CHEAP_MODEL \
  claude-haiku-4-5-20251001 "$context" \
  >>"$dir/.session-end.log" 2>&1 &

exit 0
