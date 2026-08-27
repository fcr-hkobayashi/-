# 引き継ぎ書（Handoff）

このリポジトリは、複数の Claude Code セッションで開発してきた **4 つの Web アプリを含むモノレポ** です。
別環境の Claude Code（他社／他アカウント含む）や、別の担当者がそのまま作業を引き継げるように、
プロジェクト全体の現状・構成・続きの進め方をこの 1 ファイルにまとめています。

> **前提**: 新しい Claude Code セッションには過去の会話履歴は引き継がれません。
> この `HANDOFF.md` と各アプリの `README.md` を読めば、続きの開発ができるように書いています。
> まずはこのファイル → 対象アプリの `README.md` の順で読んでください。

- **リポジトリ**: `github.com/fcr-hkobayashi/-`
- **デフォルトブランチ**: `main`
- **この引き継ぎ書のブランチ**: `claude/handoff-documentation-giurd1`
- **開発スタイル**: 各機能を `claude/...` ブランチで作り、`main` へ Pull Request でマージ（履歴の PR #1〜#21 参照）
- **言語 / 対象ユーザー**: すべて日本語 UI、日本国内の個人ユーザー向け

---

## 0. 最初にやること（新しい環境でのセットアップ）

いずれのアプリもビルド不要。Node.js（v20 以上を推奨）と Python3 があれば動きます。

```bash
git clone https://github.com/fcr-hkobayashi/-.git
cd -

# 静的アプリ（ai-secretary-app / ai-vocab-zukan / japan-history-map-app）はこれだけで確認可能
cd ai-vocab-zukan && python3 -m http.server 8000   # http://localhost:8000

# used-market-app のみ Node サーバーが必要
cd ../used-market-app && node server.mjs            # http://127.0.0.1:4173
```

- 秘密情報（APIキー・トークン類）はリポジトリには含まれません。デプロイ先の環境変数として設定します（各アプリの節を参照）。
- Claude API を使う箇所のモデルは `claude-sonnet-5` を指定しています。

---

## 1. リポジトリ構成

```
/
├── PRODUCT.md               … used-market-app（みらいや査定）のプロダクト定義・デザイン方針
├── HANDOFF.md               … この引き継ぎ書
├── ai-secretary-app/        … 【アプリ①】AI秘書メモ（音声メモ + LINE/Notion 連携）
├── ai-vocab-zukan/          … 【アプリ②】AI用語ずかん（単語帳 + Googleカレンダー連携）
├── japan-history-map-app/   … 【アプリ③】日本史マップ（地図年表 + クイズ）
└── used-market-app/         … 【アプリ④】みらいや査定（買取相場ツール・要ログイン）
```

各アプリは独立してデプロイします。Vercel でインポートする静的アプリは
**Root Directory をそのアプリのフォルダ名に設定**するのが必須です（モノレポのため）。

---

## 2. アプリ①: AI秘書メモ（`ai-secretary-app/`）

**何をするアプリか**: 運転中などに話しかけるだけで、内容を「仕事 / 新しいアイデア / 明日やること / 後で調べること」に
自動分類して記録し、あとでスマホでまとめて確認できるハンズフリー音声メモ。

- **技術**: 静的サイト（HTML/CSS/JS）+ Vercel Serverless Functions（`/api`）+ Vercel Cron
- **タブ構成**: 録音（`tab-record`）/ 確認（`tab-review`）/ 設定（`tab-settings`）の 3 タブ
- **保存先**: 基本はブラウザの `localStorage`。加えて夜の自動レポート用にサーバー（Vercel KV / Upstash Redis）へ同期
- **自動レポート**: 毎晩 20:00 JST に Vercel Cron が起動 → Claude で要約 → LINE 送信 + Notion 1ページ保存
  - `vercel.json` の cron は `"0 11 * * *"`（UTC 11:00 = JST 20:00）

### 主なファイル
| ファイル | 役割 |
|---|---|
| `js/app.js` | 画面状態管理・Web Speech API 音声認識・UI |
| `js/classifier.js` | キーワードベースの自動分類（`KEYWORDS` を編集して精度調整） |
| `js/storage.js` | localStorage 読み書き |
| `js/claude.js` | 確認タブの手動要約（ブラウザから直接 Anthropic API を呼ぶ・任意） |
| `js/sync.js` | 保存時にサーバー `/api/entries` へ同期（同期合言葉 `HARDCODED_SECRET` を内蔵） |
| `api/entries.js` | メモを KV に保存/取得する API |
| `api/cron/daily-report.js` | 20時に要約→LINE送信→Notion保存を実行 |
| `lib/kv.js` `lib/date.js` `lib/claude-server.js` `lib/line.js` `lib/notion.js` | サーバー側ヘルパー |

### 引き継ぎに必要な設定（Vercel 環境変数）
LINE / Notion / 夜レポートを使う場合のみ必要（アプリ本体はこれ無しでも動く）。

| 変数名 | 用途 |
|---|---|
| `KV_REST_API_URL` / `KV_REST_API_TOKEN` | Vercel Storage（Upstash Redis）接続。DB を Connect すると自動追加 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API の長期アクセストークン |
| `ANTHROPIC_API_KEY` | 夜レポート生成用の Claude APIキー |
| `SYNC_SECRET` | `js/sync.js` 内の `HARDCODED_SECRET`（現状 `466c50e83cc9ad26f55944a6534859`）と一致させる |
| `CRON_SECRET` | （任意）Cron 以外からの呼び出しを拒否する合言葉 |
| `NOTION_TOKEN` / `NOTION_DATABASE_ID` | （任意）Notion アーカイブ用 |

- **セキュリティ注意**: `SYNC_SECRET` はフロントの JS に埋め込まれているため完全な防御ではない。URL を他人に共有すると同じ DB・同じ LINE に混ざる（ユーザー分離機能なし）。本格運用時はユーザー分離・認証の追加が必要。
- 詳細な取得手順は `ai-secretary-app/README.md` に記載。

---

## 3. アプリ②: AI用語ずかん（`ai-vocab-zukan/`）

**何をするアプリか**: AI 用語を「図鑑を集める」感覚で覚える単語帳。カードをめくって意味・たとえ話・使用例を確認し、
「収集」してコレクションを進める。4択クイズと、Google カレンダーへの学習リマインド登録も可能。

- **技術**: 完全な静的サイト（HTML/CSS/JS のみ、サーバー無し）。Vercel などにそのまま配置
- **タブ構成**: 図鑑（`zukan`）/ クイズ（`quiz`）/ カレンダー（`calendar`）の 3 タブ
- **収録**: 9 カテゴリ・128 語（`機械学習` カテゴリに ML 実務用語 16 語を追加済み）
- **進捗保存**: 収集状況・クイズのベスト記録は `localStorage`

### 主なファイル
| ファイル | 役割 |
|---|---|
| `js/data.js` | 用語データ（`TERMS` 配列）とカテゴリ（`CATEGORIES`）。**用語追加はここに追記するだけ**で図鑑・クイズに自動反映 |
| `js/app.js` | 図鑑・クイズのロジック、検索、学習ストリークバナー、読みの音声再生 |
| `js/calendar.js` | Google カレンダー連携（OAuth・学習セッション自動登録） |

### 用語データの形式
```js
{ id: 'category-13', category: 'basics', term: '用語名', reading: '読み方',
  summary: '簡単な説明（カード表面）', analogy: 'たとえ話', example: '使用例' }
```

### 引き継ぎに必要な設定（Google カレンダー連携）
- `js/calendar.js` に **Google OAuth Client ID がハードコード**されています
  （現状: `979731749526-qvnhd4em0gnpscfpj5hagimk4erntlcn.apps.googleusercontent.com`）。
- スコープ: `https://www.googleapis.com/auth/calendar.events`
- **別環境／別ドメインで動かす場合の必須作業**: Google Cloud Console の OAuth クライアントで、
  デプロイ先の URL を **承認済みリダイレクト URI / 承認済み JavaScript 生成元**に登録すること。
  リダイレクト URI はアプリ側で `location.origin + location.pathname` を使用（リダイレクトモード）。
- 別プロジェクトで運用するなら、自分の Google Cloud プロジェクトで新しい Client ID を発行し、この定数を差し替えるのが望ましい。

---

## 4. アプリ③: 日本史マップ 縄文-現在（`japan-history-map-app/`）

**何をするアプリか**: 日本地図上のピンで、縄文時代〜現在の主な出来事を「いつ・どこで」起きたかを確認できる学習アプリ。
年号/場所/できごと/内容/人物/ミックスの 6 モードのクイズ付き（簡易間隔反復で苦手を優先再出題）。

- **技術**: 完全な静的サイト（サーバー無し）。GitHub Pages などにもそのまま置ける
- **進捗保存**: 正答率などは `localStorage`
- **出典**: 文科省 学習指導要領の標準範囲に沿う（教科書本文は不使用）

### 主なファイル
| ファイル | 役割 |
|---|---|
| `js/data.js` | 出来事データ（`EVENTS`）・カテゴリ・時代（`ERAS`） |
| `js/map.js` | 簡略化した日本地図の描画とピン配置（同地点は自動で少しずらす） |
| `js/app.js` | 地図タイムライン画面のロジック |
| `js/quiz.js` | クイズ機能 |

### 出来事データの形式
```js
{ id, year, title, pref, lon, lat, cat, desc, figure? }
// year は西暦（紀元前は負の値。例: 紀元前660年 → -660）
// figure（任意）を付けると「人物当て」クイズに出題される
```

---

## 5. アプリ④: みらいや査定 Web公開版（`used-market-app/`）

**何をするアプリか**: 中古買取店「みらいや」の査定スタッフ向けツール。オークファン/ヤフオク/メルカリ等の相場テキストを
貼り付けて中央値を出し、手数料・目標粗利・リスク控除から買取提示額を計算・保存する。**プロダクト定義は `PRODUCT.md` を参照**。

- **技術**: **Node.js サーバー（`server.mjs`, ESM）付き**。ここだけ静的サイトではない
- **ログイン**: ID/パスワードでログインしたユーザーのみ閲覧可。`admin`/`editor` 権限は `/editor` から本体（`index.html`/`styles.css`/`app.js`）を編集可能
- **認証**: パスワードは `users.json` に PBKDF2 ハッシュ（210,000 回, sha256）で保存。ログインは署名付き Cookie（365日）
- **デザイン方針（PRODUCT.md 抜粋）**: 白背景基調、紺はヘッダー・主ボタン・選択状態のみ、iOS 風のクリーンな操作感。
  「全面ダークブルー」「SaaS 風の装飾」「クリーム/ベージュ背景」は **明確な NG**。金額と件数が最初に目に入る階層。

### 起動・デプロイ
```bash
node server.mjs                              # ローカル: http://127.0.0.1:4173
HOST=0.0.0.0 PORT=4173 node server.mjs       # 公開サーバー
```
- 公開は **Render 推奨**（`render.yaml` 同梱。`npm start` で起動）。手順は `used-market-app/DEPLOY.md`
- 環境変数: `HOST` / `PORT` / `PUBLIC_EDITOR`（`true` でログイン無し公開編集。通常 OFF）

### 引き継ぎに必要な設定
- **`index.html` を直接静的公開しない**。必ず `server.mjs` 経由で公開（ログイン制が効かなくなる）
- **初期パスワードは必ず変更**する。変更手順（`users.json` の salt/hash 再生成）は `used-market-app/README.md`
- 本格運用ではセッション保存・操作ログ・バックアップ・二要素認証の追加が必要（現状は簡易実装）

---

## 6. これまでの経緯（PR 履歴の要約）

`main` の履歴から読み取れる開発の流れ（新しい順の主なもの）:

- みらいや査定を最初に構築 → ライトテーマへ刷新、Cookie ログイン（365日）化
- 日本史マップを追加（PR #1〜#3）: 縄文〜現在へ拡張、内容当て・人物当てクイズ追加
- AI用語ずかんを追加（PR #4）→ ML 用語 16 語追加、検索、学習ストリーク、読みの音声再生、視認性改善
- AI秘書メモを追加（PR #5〜#8）: 夜の LINE 自動レポート（Cron + Claude 要約）、同期失敗の可視化、同期合言葉の内蔵化
- Google カレンダー連携（PR #9〜#19）: 学習リマインド登録、登録内容のアプリ内確認、カレンダータブ、エラー可視化、スケジュール再作成時の重複セッション削除
- Notion 自動アーカイブ（PR #20）、モバイルの白画面対策として Google 認証をリダイレクトモードへ変更（PR #21）

---

## 7. 続きの開発を始めるときの手順（推奨フロー）

1. `main` から機能ブランチを切る: `git checkout main && git pull && git checkout -b claude/<機能名>`
2. 対象アプリのフォルダで作業（ビルド不要。上記のローカル起動で即確認）
3. 変更をコミットし、`git push -u origin <ブランチ名>`
4. 必要なら Pull Request を作成して `main` へマージ（本リポジトリの既存フロー）
5. Vercel / Render は `main` への push で自動再デプロイ（各アプリの Root Directory 設定に注意）

### 未対応・今後の拡張候補（ロードマップ）
- **AI秘書メモ**: ④ 仕事の振り返り（週次・月次のメモ集計、傾向のグラフ化）／ ユーザーごとのデータ分離・認証
- **みらいや査定**: セッション保存・操作ログ・バックアップ・二要素認証（本格運用向け）
- **共通**: 秘密情報（OAuth Client ID / 同期合言葉）を各運用者ごとに自前のものへ差し替える

---

## 8. 引き継ぎ時のチェックリスト（別環境の Claude Code / 担当者向け）

- [ ] このリポジトリを clone し、各アプリをローカルで起動して動作確認した
- [ ] どのアプリを触るか決め、そのアプリの `README.md` を読んだ
- [ ] デプロイ先（Vercel / Render）と Root Directory 設定を把握した
- [ ] 必要な秘密情報を自分の環境で用意した:
  - [ ] AI秘書メモ: KV / LINE / ANTHROPIC_API_KEY / SYNC_SECRET（+ 任意で Notion・CRON_SECRET）
  - [ ] AI用語ずかん: Google OAuth Client ID とリダイレクト URI 登録（別ドメインなら必須）
  - [ ] みらいや査定: `users.json` の初期パスワード変更、`PUBLIC_EDITOR` の扱い
- [ ] 機能ブランチを切って作業する運用に合わせた

---

_この引き継ぎ書はリポジトリの実際の状態（コード・コミット履歴・各 README）に基づいて作成しています。
仕様の詳細は各アプリの `README.md` と `PRODUCT.md` が一次情報です。_
