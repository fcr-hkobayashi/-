#!/usr/bin/env bash
# Shared helper: run a headless Claude Code pass over the vault with a prompt.
#
# Usage: _run.sh <prompt-file> <model-env-var-name> <default-model> [extra prompt text...]
# Env:
#   SB_CLAUDE_BIN   claude binary (default: claude)
#   SB_CHEAP_MODEL  model for routine passes (default: claude-haiku-4-5-20251001)
#   SB_BIG_MODEL    model for synthesis     (default: claude-opus-4-8)
#   SB_DRY_RUN=1    print the command instead of running it
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vault_dir="$(cd "$script_dir/.." && pwd)"

prompt_file="$1"; model_var="$2"; default_model="$3"; shift 3
extra="${*:-}"

claude_bin="${SB_CLAUDE_BIN:-claude}"
model="${!model_var:-$default_model}"

prompt="$(cat "$script_dir/$prompt_file")"
if [ -n "$extra" ]; then
  prompt="$prompt

Extra context for this run:
$extra"
fi

cmd=("$claude_bin" -p "$prompt"
  --model "$model"
  --add-dir "$vault_dir"
  --permission-mode acceptEdits)

if [ "${SB_DRY_RUN:-0}" = "1" ]; then
  printf 'DRY RUN — would run:\n'
  printf '  cd %q\n' "$vault_dir"
  printf '  %q ' "${cmd[@]}"; echo
  printf '\n--- prompt ---\n%s\n' "$prompt"
  exit 0
fi

cd "$vault_dir"
exec "${cmd[@]}"
