# Obsidian × Claude Code セカンドブレイン

Obsidian の Vault（メモの保管庫）を、Claude Code が読み書きできる「第二の脳」として運用するための一式です。
メモは人間が書き殴り、整理・要約・リンク付け・検索は Claude Code に任せます。

> 参考にした記事: `couples-navi.com` の「Claude Code × Obsidian セカンドブレイン構築」記事。
> （※ 構築時点でこのリモート環境からは当該サイトへアクセスできなかったため、
> 一般的な Obsidian × Claude Code 連携パターンと PARA + Zettelkasten 方式で構成しています。
> 記事固有の手順があれば、内容を貼っていただければこの構成に反映します。）

---

## 何ができるようになるか

- 「今日のデイリーノート作って」→ テンプレから自動作成
- 「Inbox を整理して」→ 未整理メモを適切なフォルダへ分類＋リンク付け
- 「先週の学びをまとめて」→ Vault 全体を横断検索して要約
- 「この長いメモを永久ノートにして」→ 自分の言葉に圧縮＋関連ノートへ相互リンク
- 「未完了タスクを集めて」→ 全ノートの `- [ ]` を集約

---

## フォルダ構成

| フォルダ | 役割 |
|----------|------|
| `00_Inbox/` | 未整理メモ。とりあえず全部ここ |
| `10_Daily/` | デイリーノート（`YYYY-MM-DD.md`） |
| `20_Projects/` | 締切のある進行中の案件 |
| `30_Areas/` | 継続的に責任を持つ領域（健康・家計・仕事など） |
| `40_Resources/` | 興味・参考資料・知識のストック |
| `50_Archive/` | 完了・非活性 |
| `60_Permanent/` | 自分の言葉で書き直した永久保存ノート |
| `90_Templates/` | テンプレート |
| `.claude/commands/` | Claude Code のスラッシュコマンド |
| `CLAUDE.md` | Claude Code の運用ルール（自動読み込み） |

PARA（Projects / Areas / Resources / Archive）で情報を分類し、Zettelkasten（永久ノート＋リンク）で
知識を育てるハイブリッド構成です。

---

## セットアップ手順

### 1. このリポジトリを手元に用意する
このリポジトリを PC にクローン（またはプル）します。`obsidian-second-brain/` フォルダが Vault 本体です。

### 2. Obsidian をインストールして Vault を開く
1. [Obsidian 公式サイト](https://obsidian.md) からアプリをインストール。
2. Obsidian を起動 → 「Open folder as vault（フォルダを Vault として開く）」を選択。
3. この `obsidian-second-brain/` フォルダを指定する。

これだけで Obsidian 側の準備は完了です。`[[リンク]]` のグラフ表示やタグ検索がすぐ使えます。

#### （任意）テンプレート機能を有効化
Obsidian 設定 → 「コアプラグイン」→「Templates」を ON → テンプレートフォルダを `90_Templates` に設定。
`{{date}}` などは Obsidian のテンプレート機能／Claude Code の置換の両方で使えます。

### 3. Claude Code から Vault を操作する

**方式A（推奨・最もシンプル）: ファイルシステム直操作**
ターミナルで Vault フォルダに入って Claude Code を起動するだけ。追加設定は不要です。
```bash
cd obsidian-second-brain
claude
```
Claude Code は起動時に `CLAUDE.md` を自動で読み込み、ルールに沿ってノートを読み書きします。
`.claude/commands/` のスラッシュコマンド（`/daily` `/inbox-zero` `/weekly-review` `/permanent`）も使えます。

**方式B（任意）: MCP で Obsidian と接続**
Obsidian を開いたままリアルタイムに連携したい場合は、MCP サーバー経由で接続できます。

1. Obsidian のコミュニティプラグイン **「Local REST API」** をインストールし、有効化して API キーを発行。
2. Claude Code に Obsidian MCP サーバーを登録する（例: `mcp-obsidian`）:
   ```bash
   claude mcp add obsidian -- npx -y mcp-obsidian
   ```
   ※ 使う MCP サーバーの README に従い、API キーや Vault パスを環境変数で渡してください。
3. Claude Code 内で `/mcp` を実行し、ツールとして認識されているか確認する。

> どちらの方式でも CLAUDE.md の運用ルールはそのまま効きます。まずは**方式A**から始めるのがおすすめです。

---

## 使い方（コマンド例）

Claude Code を Vault 内で起動したら、次のように話しかけます。

```
/daily                     # 今日のデイリーノートを作成
/inbox-zero                # Inbox を整理して各フォルダへ振り分け
/permanent 40_Resources/Obsidian使い方.md   # 指定メモを永久ノート化
/weekly-review             # 直近7日の週次レビュー
```

自然文でもOK:
- 「`00_Inbox` に書いた買い物のアイデアを、Areas の家計ノートにまとめて」
- 「複利について書いた永久ノートと、投資メモをリンクしておいて」
- 「今週 status を done にしたプロジェクトを Archive に移して」

---

## Google Meet 連携（会議メモの自動取り込み）

Google カレンダーの Meet 予定を、Obsidian の会議ノート（`15_Meetings/`）に取り込みます。

### 手動で実行
Vault 内で Claude Code を起動し、Google Calendar / Google Drive コネクタが有効な状態で:
```
/meet-sync
```
前回同期日〜今日の Meet 予定を拾い、`15_Meetings/YYYY-MM-DD-会議名.md` を生成します。
- **あなたが主催した Workspace の Meet** → Transcript 本文まで取り込み、要約・アクションを自動生成。
- **ゲスト参加の Meet** → Transcript は主催者 Drive 所有で本文取得不可のことがあり、その場合はリンクのみ残します（手元で開いて追記）。

### 自動ルーティン（毎朝）
毎朝 **07:07 JST** に上記を自動実行し、リポジトリへコミット・プッシュする Routine を登録済みです
（あなたは PC で `git pull` するだけで Obsidian に反映）。

> ⚠️ **重要な前提**: この自動セッションが動くには **Google Calendar / Google Drive コネクタへのアクセス**が必要です。
> プログラム経由で作成した Routine にはコネクタが自動付与されない設定になっているため、確実に動かすには
> **claude.ai の「ルーティン（Routines）」UI から、同じ内容のルーティンを作成／有効化**してください
> （UI 作成なら、あなたのアカウントで有効な Google コネクタが自動で紐づきます）。
> コネクタが無い朝は、セッションは何も壊さず「コネクタ未接続のため中断」と報告して終了します（誤った内容は書きません）。
>
> コネクタが使えない間の確実な運用は、上の **手動 `/meet-sync`**（コネクタ有効なセッションで実行）です。

同期の重複防止のため、取り込み済みの予定は `15_Meetings/.meet-sync-state.json` で管理しています。

---

## Claude会話の取り込み（claude.ai → Obsidian）

claude.ai の会話履歴は API/コネクタから直接読めないため、**公式エクスポートを一度取得**して取り込みます。
一度取り込めば、次回以降は同じ手順で差分だけ追加されます（uuid で重複スキップ）。

### 手順
1. **エクスポート依頼**: claude.ai → 設定 → プライバシー →「データをエクスポート（Export data）」。
   数分〜数十分後にダウンロードリンクがメールで届く。
2. **zip を解凍**して `conversations.json` を取り出す。
3. **Claude Code に渡す**。次のいずれか:
   - `conversations.json` を Vault の `_import/` に置いて `/claude-import` を実行、または
   - Google Drive にアップロードし、コネクタ有効なセッションで `/claude-import`（Drive から自動取得）。
4. 会話は `40_Resources/ClaudeChats/` に「1会話=1ノート」で入り、`_ClaudeChats索引.md` からたどれる。
5. 重要な会話は `/permanent` で `60_Permanent/` に要約・昇華する。

### 補足
- 生の `conversations.json` は個人情報を含むため `.gitignore` 済み（ノートだけコミット）。
- 完全自動化は不可（エクスポートが手動＝メール配信のため）。定期的にエクスポートを `_import/` か
  Drive に置く運用にすれば、`/claude-import` で半自動的に最新化できる。

### Claude Code（CLI）の記録も取り込む
claude.ai のブラウザ会話とは別に、Claude Code のローカルセッション記録
（`~/.claude/projects/**/*.jsonl`）も取り込めます。**記録が実在する自分の PC で**:
```
python3 tools/claude_code_import.py            # ~/.claude/projects 全体
# または
/claude-code-import
```
→ `40_Resources/ClaudeCode/` に「1セッション=1ノート」で入り、`_ClaudeCode索引.md` からたどれます。
（リモート実行環境ではその環境分の記録しか無く、コピーが制限されることがあります。全記録は PC 実行が確実。）

---

## 運用のコツ

1. **とにかく Inbox に書く** — 分類は後で Claude に任せる。書く摩擦を減らすのが最優先。
2. **週1で `/inbox-zero` と `/weekly-review`** — これだけで Vault が腐らない。
3. **永久ノートは「自分の言葉」で** — コピペではなく圧縮。ここが第二の脳の価値になる。
4. **リンクを恐れない** — 迷ったらリンク。フォルダは1つ、リンクは複数。
5. **CLAUDE.md を育てる** — 使いにくい所に気づいたらルールを更新する。

---

## ファイル構成の補足
各フォルダの `_about.md` にそのフォルダの使い方を書いています。空フォルダには `.gitkeep` を置いています。
