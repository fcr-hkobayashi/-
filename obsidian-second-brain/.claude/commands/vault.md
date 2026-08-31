---
description: Obsidian Vault の現状（件数・最近の更新・滞留）を確認する
---

> **対象 Vault**: `（このVaultのルート）`

セカンドブレインの現状を確認して報告してください。

手順:
1. Vault ルート（上記パス）で以下を集計する。
   - 各フォルダ（`00_Inbox` `10_Daily` `15_Meetings` `20_Projects` `30_Areas` `40_Resources` `50_Archive` `60_Permanent`）のノート数
   - 直近7日間に更新されたノート（`find . -name '*.md' -mtime -7`）
   - `00_Inbox/` の滞留メモ数（`_about.md` は除く）
   - 全ノートの未完了タスク `- [ ]` の総数と、その内訳（ファイル別）
2. Git の状態（`git status --short` / 未プッシュのコミット）も確認する。
3. 結果を表で報告し、必要なら次のアクション（`/inbox-zero` `/weekly-review` `/daily`）を提案する。
4. 読み取りのみ。このコマンドではノートを変更しない。
