---
description: 取り込み済みの参考動画/ツイートを読んで、編集の型・手順を references/LEARNED.md に学習として追記する
argument-hint: [references/learn 配下のスラッグ（省略時は未学習すべて）]
---
`references/learn/<slug>/`（video.mp4・transcript.txt・meta.json・frames/・contact.jpg）を読んで学習する。
未取り込みの URL があれば先に `tools/learn.sh <URL>` を実行する（X/YouTube は yt-dlp で取得）。

1. meta.json（投稿文・投稿者）、transcript.txt、contact.jpg、必要な frames/ を読む。
2. 次を `references/LEARNED.md` に **スラッグ単位の節として追記**（既存の節は消さない）:
   - 出典（URL・投稿者・日付）と一言要約
   - 使っているツール・手順（再現できる粒度で）
   - 編集の型（構成・カット間隔・テロップ・音・演出）。数値があれば書く
   - 自分たちの運用（`ad` パイプライン・REFERENCE_STYLE.md）に **取り入れられる点／合わない点**
3. 取り入れる価値が高いものは、REFERENCE_STYLE.md への反映案を提示してユーザーの承認を取る（勝手に基準は変えない）。
4. 第三者の動画なので、文言・素材は流用せず型・手法だけ学ぶ。
