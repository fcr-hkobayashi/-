# CLAUDE.md — セカンドブレイン運用ルール

このファイルは、Claude Code がこの Obsidian Vault を「第二の脳（Second Brain）」として
読み書きする際の運用ルールです。Claude Code はセッション開始時にこのファイルを自動で読み込みます。
**ノートを作成・更新・検索する前に、必ずこのルールに従ってください。**

---

## 1. この Vault の目的

- 日々の思考・メモ・学び・タスクを一箇所に蓄積し、後から再利用できる「知識の外部記憶」を作る。
- Claude Code が、メモの整理・要約・リンク付け・検索・棚卸しを自動で手伝う。
- 人間は「書き殴る」ことに集中し、整理と構造化は Claude Code に任せる。
- **`70_Claude/CONTEXT.md` に「私は誰で、いま何をしているか」を書いてある。
  提案・要約・整理をする前に必ず読むこと**（このファイルが「どう書くか」、CONTEXT.md が「誰のために書くか」）。

---

## 2. フォルダ構成（PARA + Zettelkasten）

```
obsidian-second-brain/
├── CLAUDE.md          # このファイル（運用ルール）
├── README.md          # セットアップ手順・使い方
├── 00_Inbox/          # 未整理のメモ。とりあえず全部ここに入れる
├── 10_Daily/          # デイリーノート（YYYY-MM-DD.md）
├── 15_Meetings/       # Google Meet 予定から自動生成した会議ノート
├── 20_Projects/       # 締切と目標がある進行中の案件（PARA: Projects）
├── 30_Areas/          # 継続的に責任を持つ領域（PARA: Areas）例: 健康, 家計, 仕事
├── 40_Resources/      # 興味・参考資料・知識のストック（PARA: Resources）
├── 50_Archive/        # 完了・非活性になったもの（PARA: Archive）
├── 60_Permanent/      # 自分の言葉で書き直した永久保存ノート（Zettelkasten）
├── 70_Claude/         # Claude の作業領域（CONTEXT.md / memory / outputs）
├── 90_Templates/      # ノートテンプレート
└── .claude/commands/  # Claude Code のカスタムスラッシュコマンド
```

**数字プレフィックスの意味**: フォルダを情報の「流れ」順（Inbox → 整理 → 永久保存）に並べるため。

---

## 3. ノート命名規則

| 種類 | 命名規則 | 例 |
|------|----------|-----|
| デイリーノート | `YYYY-MM-DD.md` | `2026-08-21.md` |
| Inbox メモ | `YYYY-MM-DD-短いタイトル.md` | `2026-08-21-会議アイデア.md` |
| プロジェクト | `プロジェクト名.md` | `確定申告2026.md` |
| 永久ノート | `内容を一文で表すタイトル.md` | `複利は時間を味方につける.md` |
| 参考資料 | `対象名.md` | `Obsidian使い方.md` |

- ファイル名・見出しは**日本語でよい**。スペースは使わず、必要なら全角・ハイフンでつなぐ。
- 永久ノートのタイトルは「主張が一文で分かる」ものにする（後で検索・リンクしやすい）。

---

## 4. すべてのノートに付ける frontmatter

ノートを新規作成するときは、必ず先頭に YAML frontmatter を付けること。

```yaml
---
title: ノートのタイトル
created: 2026-08-21
updated: 2026-08-21
tags: [タグ1, タグ2]
type: daily | inbox | project | area | resource | permanent
status: active | done | archived
---
```

- `created` は変更しない。更新するたびに `updated` を今日の日付に更新する。
- `tags` は既存タグを優先して再利用する（新規乱立を避ける）。迷ったら `#未分類` を付ける。

---

## 5. リンクとタグの方針（ここが第二の脳の肝）

- ノート同士は Obsidian の **`[[ウィキリンク]]`** で積極的につなぐ。
  - 例: 「複利」に触れたら `[[複利は時間を味方につける]]` とリンクする。
- 新しい概念が出てきたら、まだノートが無くてもリンクを張っておく（未作成リンク＝将来の種）。
- タグは「横断的な観点」に使う（例: `#アイデア` `#要ToDo` `#読書メモ`）。
- **フォルダは1つ、リンクは複数**。分類に迷ったら Inbox に置き、リンクで関係を表現する。

---

## 6. Claude Code に依頼できる代表的な作業

以下を頼まれたら、このルールに従って自動で実行してよい：

1. **Inbox の整理**: `00_Inbox/` のメモを読み、内容に応じて適切なフォルダへ移動し、
   frontmatter・タグ・`[[リンク]]` を付与する。移動前に必ず内容を確認する。
2. **デイリーノート作成**: `90_Templates/デイリーノート.md` を元に本日分を `10_Daily/` に作る。
3. **要約・永久ノート化**: 長いメモや資料を読み、要点を自分の言葉に圧縮した永久ノートを
   `60_Permanent/` に作り、元メモへ `[[リンク]]` を張る。
4. **横断検索・棚卸し**: 「先週の学びをまとめて」等の依頼に対し、日付・タグ・全文で
   Vault を検索し、関連ノートをリンク付きでまとめる。
5. **タスク抽出**: ノート中の `- [ ]` を集めて `20_Projects/` の該当ノートやデイリーに集約する。
6. **週次レビュー**: `/weekly-review` で直近7日を振り返り、未完了タスク・主要トピックを整理する。
7. **Meet 連携**: `/meet-sync` で Google カレンダーの Meet 予定を `15_Meetings/` に会議ノート化する。
   Transcript 本文が読める会議は要約・アクション抽出まで、読めない会議はリンクのみ残す（詳細は
   `.claude/commands/meet-sync.md`）。

---

## 7. Claude Code が守るべき編集ルール（重要）

- **既存ノートの本文を勝手に削除しない**。整理は「移動・追記・リンク付与」を基本とする。
  内容を削る場合は、必ず要約に置き換えたことが分かる形にし、削除理由を一言添える。
- ファイルを移動したら、その旨をユーザーに報告する（どこから→どこへ）。
- frontmatter の `created` は保持し、`updated` のみ更新する。
- 破壊的操作（多数ファイルの一括移動・削除）は、実行前に対象一覧を提示して確認を取る。
- 個人情報・機密（パスワード、口座番号など）を外部サービスに送信しない。

---

## 8. 日付の扱い

- 「今日」は実行時のシステム日付を使う。frontmatter・ファイル名の日付は必ず実日付にする。
- 相対表現（「昨日」「先週」）はシステム日付から計算する。

---

## 9. Git 運用（バックアップと同期）

この Vault は Git リポジトリ **`~/second-brain-repo`** の一部です。
**リポジトリのルートは Vault の1つ上**で、他のアプリ（`ai-secretary-app` など）と同居しています。

```
~/second-brain-repo/          ← ここが git のルート
├── obsidian-second-brain/    ← この Vault
├── ai-secretary-app/
└── ...（他プロジェクト）
```

- **コミット対象は Vault 配下だけに限定する**。`git add -A` は他プロジェクトの作業中コードまで
  巻き込むため使わない。必ず `git add obsidian-second-brain/...` のようにパスを指定する。
- ノートを追加・移動・更新したら、その作業のまとまりごとにコミットする。
  コミットメッセージは日本語でよい（例: `Inbox整理: 投資メモを40_Resourcesへ`）。
- **プッシュは勝手に行わず、実行前にユーザーへ確認する**（ルーティン実行時を除く）。
- コミットしないもの: `_import/` の生データ、`.obsidian/workspace.json`、`.DS_Store`、
  `.claude/settings.local.json`（`.gitignore` 済み）。
- 個人情報・機密を含むノートは、コミット前に内容を確認する。

---

## 10. Claude Code 活動の自動記録（毎晩 23:30）

macOS の launchd が毎晩 23:30 に `tools/daily_claude_log.sh` を実行し、次の3つを自動で行う。

1. `tools/claude_code_import.py` — その日のセッション記録を `40_Resources/ClaudeCode/` にノート化
   （`session_id` で判定するので、何度実行しても重複しない）
2. `tools/daily_claude_log.py` — その日の活動一覧を `10_Daily/YYYY-MM-DD.md` の
   「## 🤖 Claude Code 活動ログ」セクションに書き込む（デイリーノートが無ければテンプレから作成）。
   セクションは毎回まるごと置き換わるため、手で書いた他の部分は壊さない
3. Vault 配下だけを `git commit`（`10_Daily` と `40_Resources/ClaudeCode` のみ。**プッシュはしない**）

- 登録先: `~/Library/LaunchAgents/com.hkobayashi.claude-code-daily-log.plist`
- 実行ログ: `70_Claude/memory/daily_claude_log.log`（`*.log` は `.gitignore` 済み）
- 手動実行: `bash tools/daily_claude_log.sh`、または特定日だけなら
  `python3 tools/daily_claude_log.py --date 2026-08-30`
- **この自動セクション（`## 🤖 Claude Code 活動ログ` 〜 `<!-- /claude-code-log -->`）は
  手で編集しない**。翌日の実行で上書きされる。書き残したいことは「📝 メモ・気づき」へ。

---

*このルールは運用しながら育てていく。改善点に気づいたら、この CLAUDE.md 自体を更新すること。*
