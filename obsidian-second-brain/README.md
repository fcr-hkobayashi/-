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

## 運用のコツ

1. **とにかく Inbox に書く** — 分類は後で Claude に任せる。書く摩擦を減らすのが最優先。
2. **週1で `/inbox-zero` と `/weekly-review`** — これだけで Vault が腐らない。
3. **永久ノートは「自分の言葉」で** — コピペではなく圧縮。ここが第二の脳の価値になる。
4. **リンクを恐れない** — 迷ったらリンク。フォルダは1つ、リンクは複数。
5. **CLAUDE.md を育てる** — 使いにくい所に気づいたらルールを更新する。

---

## ファイル構成の補足
各フォルダの `_about.md` にそのフォルダの使い方を書いています。空フォルダには `.gitkeep` を置いています。
