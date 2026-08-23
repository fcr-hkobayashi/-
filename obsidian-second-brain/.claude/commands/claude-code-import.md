---
description: Claude Code のローカルセッション記録を会話ノートに取り込む
---

Claude Code（CLI）の記録 `~/.claude/projects/**/*.jsonl` を、Obsidian の会話ノート
（`40_Resources/ClaudeCode/`）に一括変換します。**このコマンドはあなたのPC（記録が存在する場所）で実行してください。**

## 手順
1. 入力を決める（引数優先。無ければ `~/.claude/projects` 全体）。
2. 変換を実行:
   `python3 tools/claude_code_import.py [入力パス] --out 40_Resources/ClaudeCode`
   - 1 セッション = 1 ノート。ツール実行ログ・`<system-reminder>` 等は除外し対話本文のみ。
   - session_id で既存はスキップ（再実行しても重複しない）。索引 `_ClaudeCode索引.md` を更新。
3. 新規◯件／スキップ◯件を報告する。
4. 重要なセッションは `/permanent` で `60_Permanent/` に要約・昇華する。

## 注意
- セッション記録には個人情報・作業内容が含まれる。取り込み先はプライベートな Vault のみ。
- リモート実行環境では記録が「その環境の分」しか無く、コピーが制限されることがある。
  全記録を残したい場合は、記録が実在する自分の PC で実行するのが確実。
- 本文は改変・要約せず忠実に保存する（要約は別ノートで）。
