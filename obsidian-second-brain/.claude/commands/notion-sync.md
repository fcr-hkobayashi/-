---
description: Notion AI Notetaker の会議ノートを Obsidian の会議ノートに取り込む
---

Notion AI Notetaker（Google Meet / Zoom を録音・文字起こし・要約）が Notion に溜めた会議ノートを、
Obsidian の `15_Meetings/` に取り込みます。`tools/notion_meet_import.py` を使います。

## 手順

1. **設定を確認する**
   - `tools/notion_config.local.json` が無ければ、まだセットアップされていない。
     `tools/notion_config.example.json` を案内し、Notion の Secret（`ntn_...`）と
     Meeting Notes データベースの ID を記入してもらう（トークンはチャットに貼らせない）。

2. **取り込みを実行する**
   - 引数で期間が渡されていればそれを使う:
     - `/notion-sync --all` → 全ページ対象（初回など）
     - `/notion-sync --since 2026-09-01` → その日以降の更新のみ
   - 無ければ引数なしで実行（前回同期以降の新着だけ）:
     ```bash
     python3 tools/notion_meet_import.py
     ```
   - スクリプトが Notion ページID で重複判定するので、二重取り込みは起きない。

3. **取り込んだノートを日本語で整える（任意・推奨）**
   - 新規作成された `15_Meetings/YYYY-MM-DD-*.md` を読み、Notion の生本文（## 内容）から
     次を日本語で補う。**原文にない内容は創作しない。**
     - 「## 📝 要約（3〜5点）」を本文の先頭に追加
     - 「## ✅ 決定事項」を抽出して追加
     - 「## ☑️ アクションアイテム」を `- [ ]`（担当 / 期限）で埋める
     - 関連する `20_Projects/` や `30_Areas/` があれば `[[リンク]]` を張る
   - 長い逐語（文字起こし全文）は要点に圧縮してよいが、原文の `notion_url` は必ず残す。

4. **報告する**
   - 何件取り込んだか、スキップ（取込済）は何件かを報告する。
   - ルーティン実行時は `tools/notion_meet_sync.sh` が自動でコミットする
     （手動時は変更を `git add 15_Meetings && git commit` してよいか確認）。

## 注意
- 個人情報・機密（トークン等）を外部サービスへ送信しない。取り込みは Vault 内に書くだけ。
- 同じ会議を二重に作らない（Notion ページID で判定）。
- 日付・時刻は Asia/Tokyo で扱う。
- 全自動運用は `tools/com.hkobayashi.notion-meet-sync.plist` を launchd に登録（20分おき）。
