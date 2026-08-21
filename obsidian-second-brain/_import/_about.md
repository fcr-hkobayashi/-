---
title: _import について
tags: [meta]
---

# _import（取り込み用ドロップフォルダ）

外部データを一時的に置く場所。ここに置いたファイルは Claude Code が取り込みに使う。

- `conversations.json` … claude.ai のエクスポート。`/claude-import` が拾って会話ノート化する。
- 生の JSON/zip は `.gitignore` 済みでコミットされない（中身は個人情報を含むため）。
- 取り込みが済んだら、このフォルダのファイルは削除してよい。
