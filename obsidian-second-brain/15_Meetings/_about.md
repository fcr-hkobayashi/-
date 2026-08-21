---
title: Meetings について
tags: [meta]
---

# 15_Meetings（Meet 連携の受け皿）

Google カレンダーの Meet 予定から自動生成された会議ノートが入るフォルダ。

- 生成元: `/meet-sync`（`.claude/commands/meet-sync.md`）または定期ルーティン。
- ファイル名: `YYYY-MM-DD-会議名.md`
- 各ノートには Meet リンク・参加者・Transcript へのリンク・要約・アクションアイテムが入る。
- アクションアイテム（`- [ ]`）は `/weekly-review` や `/daily` の引き継ぎ対象になる。

## Transcript 本文について
- **あなたが主催した Workspace の Meet** → Transcript があなたの Drive に保存され、本文まで自動取り込み。
- **ゲスト参加の Meet**（主催が他社）→ Transcript は主催者の Drive 所有のため本文は自動取得できないことがある。
  その場合はノートに Transcript の**リンク**を残すので、手元で開いて追記する。
