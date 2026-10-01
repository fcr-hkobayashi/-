# video-ad-studio — エージェント向け作業ルール（Codex / Claude Code 共通）

みらいや（買取店）の縦型動画広告（9:16・1080×1920）を AI で編集する作業場。
**表現の基準は `kaitori-ad-style` スキル**、実作業は `ad` コマンド（`bin/ad`）で行う。

## パイプライン
```
projects/<name>/input/ に素材 → ad all <name>
  transcribe  文字起こし（ElevenLabs Scribe。キーが無ければローカル Whisper large-v3）
  plan        無音・フィラー・言い直しのカット案 → edit/cut_plan.md, edit/edl.json   ← ここで人の承認待ち
  approve     承認
  cut         1080×1920 に切り出し（30ms フェード・波形スナップ・HDR→SDR）→ edit/cut.mp4
  compose     HyperFrames でテロップ/SE/ズーム/CTA → edit/hf/index.html
  render      レンダリング＋ -14 LUFS → output/<name>_<秒>s.mp4
  qa          仕様・フレーム(1秒毎)・音量・再文字起こし照合・表現チェック → output/qa_report.md
```

## ハードルール
1. **カット案はユーザーの承認なしに実行しない**（`ad approve` はユーザーが OK と言ってから）。
2. edl.json を直すときは単語境界に合わせ、前後 30〜200ms の余白を残す。
3. テロップ・CTA はセーフゾーン（上220/下420/左右120px）の内側だけ。
4. `ad compose` は edit/hf/index.html を**上書きする**。手で演出を足した場合は再 compose しない
   （必要なら `edit/hf/index.html` をコピーしてから）。テロップの文言修正は brand.json の glossary（恒久的な表記）か
   edit/timeline_words.json（今回だけ）を直して再 compose する。
5. HyperFrames を編集したら `npx hyperframes lint edit/hf` でエラー 0 を確認。
6. 公開物なので、書き出し後は必ず `ad qa` → レポートとコンタクトシートを確認してから報告。
7. 素材の音楽・SE は広告利用可のものだけ（CapCut 内蔵音楽は不可）。音声クローンは本人の書面同意が前提。
8. `--dangerously-skip-permissions` 等の確認スキップは使わない。

## 役割分担
- **Codex（GPT-6 Astra）= 監督**: 構成案、カット案の意味的見直し（言い直しの採否・尺調整）、
  edit/hf/index.html への演出追加（Bロール差し込み、カード、トランジション）。HyperFrames スキル群を使う。
- **Claude Code = 校閲・QA**: `/ad-qa` で誤字・ブランド表記・金額・景表法表現・はみ出しを独立に検査（ファイルは変えない）。
- **人間**: 訴求内容、最終の「間」、公開判断。

## 設定ファイル
- `brand/brand.json` — 色・フォント・テロップ寸法・セーフゾーン・強調語・表記辞書(glossary)・NG表現
- `projects/<name>/brief.json` — 目的・目標秒数・CTA・BGM・SE・ズーム量・メモ
- `sfx/pop.*` `sfx/kira.*` `sfx/whoosh.*` を置くと自作SEの代わりに使う
- `brand/logo.png` を置くと右上にロゴを表示
