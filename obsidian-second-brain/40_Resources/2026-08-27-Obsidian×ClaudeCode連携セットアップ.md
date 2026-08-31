---
title: Obsidian × Claude Code 連携セットアップ
created: 2026-08-27
updated: 2026-08-27
tags: [obsidian, claude-code, セットアップ, 資料]
type: resource
status: active
---

# Obsidian × Claude Code 連携セットアップ

出典記事: https://couples-navi.com/2026/05/09/claude-code-obsidian-second-brain-setup/
（2026-08-27 に記事を読み、この Vault の実情に合わせて反映した記録）

## この Vault での判断

記事のフォルダ構成（`01_Projects` `02_Areas/開発` `06_Claude` 等）に**リネームはしない**。
この Vault は既に PARA + Zettelkasten で運用が始まっており、既存ノートの `[[リンク]]` が
壊れるだけで得が無いため。**記事の思想（PARA・Claude 用領域・Git バックアップ）だけを取り込む。**

| 記事 | この Vault | 状態 |
|------|-----------|------|
| `00_Inbox` | `00_Inbox` | 同じ |
| `01_Projects` | `20_Projects` | 番号だけ違う |
| `02_Areas/*` | `30_Areas` | サブフォルダは作らずリンクで表現 |
| `03_Resources/*` | `40_Resources` | 同上 |
| `04_Archive` | `50_Archive` | 同じ |
| `05_Templates` | `90_Templates` | 同じ |
| `06_Claude/CONTEXT.md, memory, outputs` | `70_Claude/` | **2026-08-27 に新規作成** |
| `Daily/` | `10_Daily` | 同じ |
| （記事に無い） | `60_Permanent` | Zettelkasten 用に独自追加 |
| （記事に無い） | `15_Meetings` | Google Meet 連携用に独自追加 |

## 済んでいること

- [x] Git 初期化・リモート登録（`~/second-brain-repo` → `github.com/fcr-hkobayashi/-`）
- [x] `.gitignore` を記事準拠に強化（`workspace.json` / `plugins/*/data.json` / `.trash/` /
      `.claude/settings.local.json` / `*.tmp` `*.log` / `.smart-env` / `.DS_Store`）
- [x] `70_Claude/`（CONTEXT.md・memory・outputs）を作成
- [x] コアプラグイン **Daily notes** の設定（フォルダ `10_Daily`、書式 `YYYY-MM-DD`、
      テンプレート `90_Templates/デイリーノート.md`）
- [x] コアプラグイン **Templates** の設定（フォルダ `90_Templates`）
- [x] `CLAUDE.md` に「Git 運用」と「CONTEXT.md を読む」ルールを追記
- [x] Claude Code 側のスラッシュコマンド（`/daily` `/inbox-zero` `/permanent` `/weekly-review`
      `/meet-sync` `/claude-import` `/claude-code-import` `/vault` `/vault-sync`）

## 残っていること（Obsidian の画面から手動で行う）

コミュニティプラグインは**まだ1つも入っていない**（`.obsidian/plugins/` が存在しない）。
記事の8選のうち、この Vault に効くものを優先順に：

1. **Obsidian Git** — 自動コミット・自動プル。⚠️ 下記の注意を読むこと
2. **Templater** — `{{date}}` 等の置換をテンプレート側で完結できる
3. **Dataview** — `20_Projects` の一覧や未完了タスクを動的に集計
4. **Tasks** — `- [ ]` を横断管理
5. **Smart Connections** — 関連ノートの自動サジェスト（`.smart-env` は gitignore 済み）
6. QuickAdd / Copilot / BRAT（+ Claudian）— 必要になったら

導入手順: 設定 → コミュニティプラグイン → 制限モードを解除 → 閲覧 → 名前で検索 → インストール → 有効化

## ⚠️ Obsidian Git を入れる前に知っておくこと

**この Vault は Git リポジトリのルートではない。** リポジトリは1つ上の `~/second-brain-repo` で、
`ai-secretary-app` など**他のアプリと同居**している。

そのため Obsidian Git の自動コミット（記事の推奨設定: 30分間隔・commit-and-sync）を
そのまま有効にすると、**開発途中の他プロジェクトのコードまで巻き込んでコミット・プッシュ**する。

対処の選択肢:

- **A. Vault を独立したリポジトリに切り出す** — 記事の前提（vault = repo）に合わせる。
  Obsidian Git の自動同期を安全に使えるようになる。他プロジェクトとは履歴が分かれる。
- **B. Obsidian Git は自動同期をオフにし、手動バックアップのみ使う**
  （`Ctrl/Cmd + P` → `Obsidian Git: Create backup`）。
- **C. Obsidian Git を入れず、Claude Code の `/vault-sync` でパスを限定してコミットする**（現状の方式）。

決めるまでは **C** で運用する。

## 記事の推奨設定（Obsidian Git・A を選んだ場合に使う値）

| 項目 | 値 |
|------|-----|
| Auto commit-and-sync interval | 30（分） |
| Auto pull interval | 30（分） |
| Push on commit-and-sync | ON |
| Pull on commit-and-sync | ON |
| Commit message on auto | `vault backup: {{date}}` |

## 記事にあった補足（この Vault では未採用）

- **Claudian**（BRAT 経由で `YishenTu/claudian` を導入）: Obsidian の中から Claude CLI を叩く
  プラグイン。ターミナルで `claude` を起動する現在の運用で足りているため保留。
- **Ollama + Copilot**（`qwen2.5` などをローカル実行）: オフライン補助。ネット接続前提の
  現運用では不要。必要になったら `ollama pull qwen2.5` から。

## 🔗 関連
- [[みらいやAI]]
- [[2026-08-27]]
