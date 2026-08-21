---
description: Google カレンダーの Meet 予定を Obsidian の会議ノートに取り込む
---

Google カレンダーの Google Meet 会議を Obsidian の会議ノートとして `15_Meetings/` に取り込みます。
Google Calendar / Google Drive の MCP コネクタを使います。

## 手順

1. **対象期間を決める**
   - 引数で期間が渡されていればそれを使う（例: `/meet-sync 2026-08-01..2026-08-21`）。
   - 無ければ「前回同期日〜今日」。前回同期日は `15_Meetings/.meet-sync-state.json` の `last_synced` を見る。
     ファイルが無ければ直近14日間を対象にする。

2. **Meet 予定を取得する**
   - `list_events`（または `search_events`）で対象期間の予定を取得。
   - 次のいずれかを満たすものだけを「会議」として扱う:
     - `conferenceUrl` に `meet.google.com` を含む、または
     - `attachments` のタイトルに `Transcript` / `Notes` / `Gemini` を含む Google Docs がある。
   - `.meet-sync-state.json` の `synced_event_ids` に既にある予定は**スキップ**（重複防止）。

3. **各会議のノートを作る**
   - ファイル名: `15_Meetings/YYYY-MM-DD-会議名.md`（会議名の `/` や記号は全角化・除去）。
   - `90_Templates/Meet会議.md` を土台にして frontmatter と本文を埋める:
     - `title` / `date` / 開始・終了時刻 / `meet_url` / 参加者 / `event_id`
     - `attachments` の Transcript/Notes Docs へのリンク
   - **Transcript 本文の取り込みを試みる**:
     - 添付 Doc の `fileUrl` から fileId を取り出し、`read_file_content` で本文取得を試す。
     - 取得できたら → 「## 要約（3〜5点）」「## 決定事項」「## アクションアイテム（`- [ ]`）」を
       日本語で生成して埋める。長い逐語は載せず要点に圧縮する。原文リンクは残す。
     - 取得できなかったら（ゲスト参加等で権限が無い）→ ノートに
       「> ⚠️ Transcript本文はAPIから取得できませんでした。下記リンクを手元で開いて追記してください。」
       と明記し、リンクだけ残す。**憶測で議事内容を創作しない。**
   - 関連する `20_Projects/` や `30_Areas/` があれば `[[リンク]]` を張る。

4. **状態を更新する**
   - `.meet-sync-state.json` の `last_synced` を今日に、`synced_event_ids` に今回処理した予定IDを追記する。

5. **報告**
   - 何件取り込んだか、うち本文まで取れたのは何件か、リンクのみは何件かを一覧で報告する。
   - （Git リポジトリとして運用している場合）変更を `git add/commit/push` してよいか確認するか、
     ルーティン実行時は自動でコミット・プッシュする。

## 注意
- 個人情報・機密を外部サービスへ送信しない。要約は Vault 内に書くだけ。
- 同じ会議を二重に作らない（`event_id` で判定）。
- 日付・時刻は Asia/Tokyo で扱う。
