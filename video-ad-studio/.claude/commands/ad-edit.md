---
description: 縦型広告を編集（文字起こし→カット案→承認→テロップ→書き出し→QA）
argument-hint: <project-name>
---
`kaitori-ad-style` スキルと AGENTS.md に従い、プロジェクト `$ARGUMENTS` の縦型広告を作る。

1. `projects/$ARGUMENTS/brief.json` を読む（無ければ `bin/ad new $ARGUMENTS` で作り、目的・CTA・尺をユーザーに聞く）。
2. `bin/ad transcribe $ARGUMENTS` → `bin/ad plan $ARGUMENTS`。
3. cut_plan.md を読み、機械判定に加えて意味的な見直し（言い直しの採否、目標秒数に収める削り案、冒頭2秒のフック）を
   日本語で提案。**ユーザーの承認を待つ**。修正指示があれば edit/edl.json を直す。
4. 承認後 `bin/ad approve` → `bin/ad cut` → `bin/ad compose` → `bin/ad render`（まず --draft で確認してもよい）。
5. `bin/ad qa $ARGUMENTS` を実行し、output/qa_report.md と edit/qa/contact_sheet.png を読んで、問題・修正案を報告。
