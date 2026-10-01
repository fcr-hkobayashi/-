---
title: 縦型動画広告AI編集パイプライン
created: 2026-10-01
updated: 2026-10-01
tags: [動画広告, AI活用, ClaudeCode, ツール]
type: resource
status: active
---

# 縦型動画広告AI編集パイプライン

みらいや（買取店）の TikTok／リール向け縦型広告を、AI でほぼ自動編集する仕組み。
コードの置き場所: `~/second-brain-repo/video-ad-studio/`（詳細は同フォルダの README.md）

## 構成（2026-10 時点の推奨構成をそのまま実装）
- **監督**: Codex（GPT-6 Astra）。構成とカット案の見直し、演出の追加
- **制作**: [[HyperFrames]]（テロップ・ズーム・CTA）＋ [[video-use]]（文字起こし・カット）
- **校閲**: Claude Code（`/ad-qa`）。誤字、ブランド表記、景表法、はみ出しのチェック
- **人間**: 訴求内容、最終の「間」、公開判断

## 使い方
1. 素材を `video-ad-studio/inbox/` に入れる → 自動でカット案まで作成され、通知が来る（launchd `com.hkobayashi.video-ad-inbox`）
2. `edit/cut_plan.md` を確認 → `ad approve <name>` → `ad all <name>`
3. `output/` に完成動画と `qa_report.md` ができる

## 型（スキル `kaitori-ad-style`）
- 0〜2秒にフック → 根拠（金額は黄色）→ ベネフィット → CTA（3〜5秒）
- テロップ: 1行最大13文字・2行まで、BudouX で文節改行
- セーフゾーン: 上220px・下420px・左右120px
- 景表法: 「業界最高値」「必ず」「何でも買取」などは使わない

## 今後やること
- [ ] ElevenLabs 有料プランの API キーを設定する（日本語の文字起こし精度が上がる）
- [ ] `brand/logo.png` を置く／紺色の正確なカラーコードを `brand.json` に反映する
- [ ] 効果音ラボなどの SE を `sfx/` に置く（任意。初期状態は自作の SE）
- [ ] 実際の素材で1本作り、型が固まったら `kaitori-ad-style` を更新する

## 関連
- 元にしたレポート: 「縦型動画広告をAIで最高品質に編集する方法（2026年10月版）」（チャットで共有されたもの）
- [[2026-08-27-Obsidian×ClaudeCode連携セットアップ]]
