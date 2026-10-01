---
description: 書き出した縦型広告を独立に検査（誤字・表記・景表法・はみ出し・音量）
argument-hint: <project-name> [動画パス]
---
プロジェクト `$ARGUMENTS` の書き出し動画を検査する。**修正案を出すだけで、ファイルは変更しない。**

1. `bin/ad qa $ARGUMENTS`（動画パス指定時は `--file`）を実行。
2. `projects/<name>/output/qa_report.md`、`edit/captions.json`、`edit/qa/contact_sheet.png` を読む。
   気になる秒は `edit/qa/frames/f_<秒+1>.png` を個別に見る。
3. 次を一覧化して報告:
   - 誤字・誤変換（特にブランド名・商品名・金額）。再文字起こしとの差分は「どちらが正しいか」を判断
   - 景品表示法上問題になりうる表現（最上級・断定・比較・期間限定）と、言い換え案
   - セーフゾーン外・文字切れ・読みにくい改行・表示時間が短すぎるテロップ
   - 音量（-14 LUFS ±1 / TP ≤ -1）・尺（brief の目標）
4. 直すべき順に優先度をつける。glossary に追加すべき表記があれば提案する。
