---
title: "Google ドライブの台本(Googleドキュメント)2件をダウンロードし、base64デコードして .md ファイル"
created: 2026-08-29
updated: 2026-08-29
session_id: agent-ad18204ea3dc6a0f6
tags: [claude-code, resource]
type: resource
status: active
source: claude-code
cwd: "/Users/hayato.kobayashi/Downloads/みらいやAI"
git_branch: HEAD
---

# Google ドライブの台本(Googleドキュメント)2件をダウンロードし、base64デコードして .md ファイル

> Claude Code セッション記録（2026-08-29 〜 2026-08-29）。ツール実行ログは除外。

### **あなた**

Google ドライブの台本(Googleドキュメント)2件をダウンロードし、base64デコードして .md ファイルに保存する仕事です。

## 手順
各fileIdについて、MCPツール `mcp__8a6d3728-acd4-4b00-b179-d0f3f1ca4910__download_file_content` を `exportMimeType: "text/plain"` で呼ぶ。返ってくるJSONの `content` フィールドは**base64エンコードされたUTF-8テキスト**。これをデコードして指定パスに保存する。

- fileId `1258va9VHwSlvE5tWjznl6zI-Gl1p5QmHxgHot6jEx2U`（2-4台本）→ `/Users/hayato.kobayashi/Downloads/2-4案件/台本.md`
- fileId `1jG6rdYB7ZZXEWxkGXXLeK_C8YrkPabl5QiY2FHwX2hw`（2-5台本）→ `/Users/hayato.kobayashi/Downloads/2-5案件/台本.md`

デコード方法: tool結果の content 文字列を一時ファイルに書き、`base64 -d`（またはpython `base64.b64decode`）でデコードして目的パスへ。**巨大なbase64をそのまま最終報告に貼らないこと**（コンテキスト節約）。

## 完了条件（自分で検証）
- 両.mdが存在し、先頭が `# 台本` で始まる読めるUTF-8日本語であること（`head -3` で確認）。
- 各ファイルの `## 【スライド` の数を数えて報告（両方とも11前後のはず）。
- 文字化けが無いこと。

最終報告は、2つのファイルパス・各行数/スライド見出し数・冒頭2行（タイトル行）だけ簡潔に。台本本文全体は貼らないこと。

### **Claude**

I'll decode both base64 strings and save them. Let me write the base64 to temp files and decode.

### **Claude**

Now let me create the target directories and decode.

### **Claude**

macOS base64 needs `-i` for input file. Let me fix.

### **Claude**

Both files decoded and verified successfully. No mojibake — clean UTF-8 Japanese.

## 完了報告

両ファイルとも正常にデコード・保存できました。

**保存先パス**
- `/Users/hayato.kobayashi/Downloads/2-4案件/台本.md`
- `/Users/hayato.kobayashi/Downloads/2-5案件/台本.md`

**検証結果**

| ファイル | 行数 | `## 【スライド` 見出し数 | 冒頭2行（タイトル行） |
|---|---|---|---|
| 2-4案件/台本.md | 192行 | 11 | `# 台本 — 第2章 制約の書き方` |
| 2-5案件/台本.md | 183行 | 11 | `# 台本 — 第2章 出力形式の指定` |

- 両方とも先頭が `# 台本` で始まる読めるUTF-8日本語（先頭にBOM付き）。
- スライド見出しは両方とも11で想定どおり。
- 文字化けなし。
