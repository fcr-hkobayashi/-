#!/bin/bash
# 日中に launchd から短い間隔で実行される（例: 20分おき）。
#   1) Notion AI Notetaker の新着会議ノートを 15_Meetings/ に取り込む（新規のみ）
#   2) Vault 配下だけを git commit（プッシュはしない）
# 手動実行もこのスクリプトでOK: bash tools/notion_meet_sync.sh
set -uo pipefail

VAULT="/Users/hayato.kobayashi/second-brain-repo/obsidian-second-brain"
REPO="/Users/hayato.kobayashi/second-brain-repo"
PY=/usr/bin/python3
GIT=/usr/bin/git
TODAY=$(date +%Y-%m-%d)

cd "$VAULT" || exit 1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') Notion同期 開始 ====="

echo "--- 1) Notion会議ノートの取り込み"
"$PY" tools/notion_meet_import.py || { echo "[warn] 取り込み失敗"; exit 0; }

echo "--- 2) Git コミット（Vault配下のみ・プッシュはしない）"
# 他プロジェクトを巻き込まないよう、必ずパスを限定する（CLAUDE.md 9節）
"$GIT" -C "$REPO" add obsidian-second-brain/15_Meetings
if "$GIT" -C "$REPO" diff --cached --quiet; then
  echo "変更なし"
else
  "$GIT" -C "$REPO" commit -q -m "自動記録: Notion会議ノート取り込み ${TODAY}" && echo "コミット済み"
fi

echo "===== 完了 ====="
