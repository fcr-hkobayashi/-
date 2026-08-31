#!/bin/bash
# 毎晩 23:30 に launchd から実行される。
#   1) Claude Code のセッション記録をノート化（新規のみ・重複はスキップ）
#   2) その日の活動サマリーをデイリーノートに追記
#   3) Vault 配下だけを git commit（プッシュはしない）
set -uo pipefail

VAULT="/Users/hayato.kobayashi/second-brain-repo/obsidian-second-brain"
REPO="/Users/hayato.kobayashi/second-brain-repo"
PY=/usr/bin/python3
GIT=/usr/bin/git
TODAY=$(date +%Y-%m-%d)

cd "$VAULT" || exit 1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 開始 ====="

echo "--- 1) セッション記録の取り込み"
"$PY" tools/claude_code_import.py --out 40_Resources/ClaudeCode || echo "[warn] 取り込み失敗"

echo "--- 2) デイリーノートへ活動サマリー"
"$PY" tools/daily_claude_log.py --date "$TODAY" || echo "[warn] サマリー失敗"

echo "--- 3) Git コミット（Vault配下のみ・プッシュはしない）"
# 他プロジェクトを巻き込まないよう、必ずパスを限定する（CLAUDE.md 9節）
"$GIT" -C "$REPO" add obsidian-second-brain/10_Daily obsidian-second-brain/40_Resources/ClaudeCode
if "$GIT" -C "$REPO" diff --cached --quiet; then
  echo "変更なし"
else
  "$GIT" -C "$REPO" commit -q -m "自動記録: Claude Code 活動ログ ${TODAY}" && echo "コミット済み"
fi

echo "===== 完了 ====="
