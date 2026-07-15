# みらいや査定 Web公開版

## 追加された機能

- ID/パスワードログイン
- ログイン済みユーザーだけがアプリを閲覧可能
- `admin` / `editor` 権限ユーザーは `/editor` からアプリ本体を編集可能
- `PUBLIC_EDITOR=true` を設定すると、ログインなしで `/editor` を公開編集できます
- 編集対象は `index.html`、`styles.css`、`app.js`
- パスワードは `users.json` に PBKDF2 ハッシュで保存

## 初期ログイン

管理者:

- ID: `admin`

編集者:

- ID: `editor`

パスワードは `users.json` のハッシュで管理しています。

## ローカル起動

```bash
node server.mjs
```

標準では以下で起動します。

```text
http://127.0.0.1:4173
```

公開サーバーでは環境変数を指定してください。

```bash
HOST=0.0.0.0 PORT=4173 node server.mjs
```

## Web公開

RenderとRailwayで公開する手順を追加しています。

[DEPLOY.md](./DEPLOY.md)

[RAILWAY_DEPLOY.md](./RAILWAY_DEPLOY.md)

## 公開時の注意

- `index.html` を直接公開しないでください。必ず `server.mjs` 経由で公開してください。
- HTTPSを使ってください。
- 初期パスワードは必ず変更してください。
- `/editor` はアプリ本体を書き換えられるため、編集者IDは信頼できる人だけに渡してください。
- `PUBLIC_EDITOR=true` は誰でも編集できる状態になるため、必要な時だけONにしてください。
- 本格運用では、セッション保存、操作ログ、バックアップ、二要素認証を追加してください。

## パスワード変更

`users.json` の `salt` と `hash` を作り直します。例:

```bash
node -e "const crypto=require('crypto'); const password='NewPasswordHere'; const salt=crypto.randomBytes(16).toString('hex'); const hash=crypto.pbkdf2Sync(password,salt,210000,32,'sha256').toString('hex'); console.log({salt,hash,iterations:210000});"
```

出力された `salt`、`hash`、`iterations` を対象ユーザーに反映してください。
