# みらいや査定 公開手順

## 推奨: Renderで公開

このアプリは静的HTMLではなく、ログイン機能付きのNode.jsアプリです。
Google Drive、GitHub Pages、Netlifyの静的ホスティングだけではログイン制が機能しません。

## 1. GitHubにアップロード

アップロードするフォルダ:

```text
outputs/used-market-app
```

この中身をGitHubリポジトリのルートに置いてください。

必要ファイル:

- `server.mjs`
- `package.json`
- `index.html`
- `styles.css`
- `app.js`
- `login.html`
- `editor.html`
- `users.json`
- `render.yaml`

## 2. RenderでWeb Serviceを作成

1. Renderにログイン
2. `New` → `Web Service`
3. GitHubリポジトリを接続
4. 設定は以下

```text
Environment: Node
Build Command: npm install
Start Command: npm start
```

環境変数:

```text
HOST=0.0.0.0
NODE_VERSION=20
```

`render.yaml` を使う場合は、Render側が自動で設定を読めます。

## 3. 公開URLを共有

Renderのデプロイが完了すると、以下のようなURLが発行されます。

```text
https://miraiya-satei.onrender.com
```

このURLを共有してください。

## 4. 初期ログイン

管理者:

```text
ID: admin
Password: MiraiyaAdmin2026!
```

編集者:

```text
ID: editor
Password: MiraiyaEdit2026!
```

公開前に必ず変更してください。

## 5. アプリ編集

ログイン後、以下にアクセスします。

```text
/editor
```

編集できるファイル:

- `index.html`
- `styles.css`
- `app.js`

## 重要な注意

- `index.html` を直接公開しないでください。
- 必ず `server.mjs` を起動できるWebサービスで公開してください。
- 初期パスワードは公開前に変更してください。
- 無料Renderは一定時間アクセスがないとスリープします。
- 本格運用ではデータベース、操作ログ、バックアップ、二要素認証を追加してください。
