---
description: claude.ai のエクスポート(conversations.json)を会話ノートに取り込む
---

claude.ai のデータエクスポートに含まれる `conversations.json` を、Obsidian の会話ノート
（`40_Resources/ClaudeChats/`）に一括変換します。

## 入力の見つけ方（優先順）
1. 引数でパスが渡されていればそれを使う（例: `/claude-import ~/Downloads/conversations.json`）。
2. `_import/` フォルダに `conversations.json`（または `*.json`）があればそれを使う。
3. Google Drive コネクタが使えるなら `search_files` で `title contains 'conversations'` の
   JSON を探し、`download_file_content` で `_import/conversations.json` に保存してから使う。
4. どれも無ければ、ユーザーにエクスポート方法（README「Claude会話の取り込み」）を案内して終了する。

## 手順
1. 上記で入力 JSON を確定する。
2. 変換スクリプトを実行する:
   `python3 tools/claude_chat_import.py <入力JSON> --out 40_Resources/ClaudeChats`
   - 1 会話 = 1 ノート。frontmatter（title/created/updated/uuid/tags）付き。
   - 既存 uuid はスキップするので、再実行しても重複しない。
   - 索引ノート `_ClaudeChats索引.md` が更新される。
3. 実行結果（新規◯件／スキップ◯件）を報告する。
4. 生の `_import/*.json` はコミットしない（`.gitignore` 済み）。ノートだけをコミット対象にする。

## 任意の後処理
- 特に重要な会話は `/permanent` で永久ノート化し、`60_Permanent/` に要約＋`[[リンク]]`を作る。
- 生ログは長いので、そのままではなく「索引 → 必要な会話だけ精読」を推奨。

## 注意
- 会話には個人情報が含まれ得る。取り込み先はプライベートリポジトリ内の Vault のみ。外部送信しない。
- 本文は改変・要約せず忠実に保存する（要約は別ノートで行う）。
