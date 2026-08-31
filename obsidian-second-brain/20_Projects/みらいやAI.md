---
title: みらいやAI
created: 2026-08-27
updated: 2026-08-27
tags: [project, 開発, みらいや]
type: project
status: active
deadline: 
---

# みらいやAI

## 🎯 ゴール（何が達成できたら完了か）
- 勤怠アプリ（attendance-app）が実運用に耐える状態でリリースできていること

## 📌 現状・背景
- 作業ディレクトリ: `~/Downloads/みらいやAI/`
- `attendance-app/` は Flask + SQLite（`app.py` / `static/css/style.css` / `static/js/app.js` / `data/attendance.db`）
- この案件のセッションから、セカンドブレイン（この Vault）を直接読み書きできるよう連携済み。
  → `~/Downloads/みらいやAI/CLAUDE.md` と `.claude/commands/` に、Vault と同じ運用ルール・
  スラッシュコマンド（`/daily` `/inbox-zero` `/permanent` `/weekly-review` `/meet-sync`
  `/claude-import` `/claude-code-import` `/vault`）を絶対パスで移植した。

## ✅ タスク
- [ ] attendance-app の残課題を洗い出す
- [ ] 開発中の決定事項をこのノートの「意思決定ログ」に残す運用を続ける

## 🧭 意思決定ログ
| 日付 | 決めたこと | 理由 |
|------|-----------|------|
| 2026-08-27 | みらいやAI の作業ディレクトリから Vault を直接操作できるようにした | 案件作業とメモ蓄積を往復せずに済ませ、知見を Vault 側に一本化するため |

## 🔗 関連ノート
- [[2026-08-21-Obsidian×ClaudeCodeセットアップ]]

## 🗄 完了後
> 完了したら frontmatter の `status` を `done` にし、`50_Archive/` へ移動する。
