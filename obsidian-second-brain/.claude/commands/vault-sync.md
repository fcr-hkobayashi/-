---
description: Vault の変更を Git にコミット（必要ならプッシュ）する
---

Obsidian Vault の変更を Git に反映してください。

## 前提（重要）
リポジトリのルートは Vault の **1つ上** `~/second-brain-repo` で、他のアプリと同居しています。
**`git add -A` は絶対に使わないこと**（他プロジェクトの作業中コードを巻き込む）。

## 手順
1. `git -C ~/second-brain-repo status --short -- obsidian-second-brain/` で Vault 配下の変更だけを確認する。
2. 変更内容をユーザーに一覧で提示する（新規 / 変更 / 削除・移動を分けて）。
3. 機密（パスワード・口座番号・APIキー等）が含まれていないか、差分をざっと確認する。
   見つかったらコミットせず報告する。
4. `git -C ~/second-brain-repo add obsidian-second-brain/` でパスを限定してステージする。
   引数でパスが渡された場合はそのパスだけを対象にする。
5. 日本語で意味の分かるコミットメッセージを付けてコミットする
   （例: `Inbox整理: 投資メモを40_Resourcesへ` / `デイリーノート追加: 2026-08-27`）。
   まとまりが複数あるなら複数コミットに分ける。
6. **プッシュは実行前に必ず確認を取る。** 現在のブランチと追跡先を示した上で聞くこと
   （`git -C ~/second-brain-repo branch -vv`）。
7. 結果（コミットハッシュ・件数・プッシュ有無）を報告する。

## 注意
- `.gitignore` 済みのもの（`_import/` の生データ、`.obsidian/workspace.json`、`.DS_Store`、
  `.claude/settings.local.json`）はコミットしない。
- コンフリクトが起きたら自動解決せず、状況を報告して指示を仰ぐ。
