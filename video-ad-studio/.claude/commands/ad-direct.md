---
description: 台本の1文ごとに「与えたい印象」を判定し、フォント・効果音・アニメの演出案を direction.json にする
argument-hint: <project-name>
---
`references/DIRECTION_SPEC.md` を読み、プロジェクト `$ARGUMENTS` の文字起こし（edit/transcripts）を1文ずつに分けて:
1. 印象（ポジ/ネガ/ニュートラル・強さ・役割）を判定。迷う文は理由つきで「要確認」にする
2. プリセット表から フォント・色・SE・アニメ・間 を割り当て、`projects/$ARGUMENTS/edit/direction.json` と
   人が読む表（文／印象／演出／理由）を出す
3. **承認前は compose に反映しない。** ユーザーが直した判定は DIRECTION_SPEC.md のプリセットに還元する提案を出す
