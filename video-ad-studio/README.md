# video-ad-studio — 縦型動画広告の AI 編集パイプライン

「Codex（GPT-6 Astra）が監督 × HyperFrames が制作 × Claude Code が校閲」構成を、`ad` コマンド 1 本で回すための作業場。

## いちばん簡単な使い方（自動）
1. 撮った縦型素材（mp4/mov）を **`inbox/` に入れる**
   - ファイル名に `30s`／`30秒` を入れると30秒版、`60s`／`60秒`／`1分` を入れると1分版のテンプレートになる（なければ15秒版）
2. 自動で文字起こし → カット案が作られ、macOS の通知が来る
3. `projects/<日付-ファイル名>/edit/cut_plan.md` を見て OK なら
   ```bash
   ad approve <name> && ad all <name>
   ```
4. `output/<name>_<秒>s.mp4` と `output/qa_report.md` ができる

## 手動 / AI と対話して使う
```bash
ad new 0101-バッグ査定 --from ~/Desktop/clip.mov   # プロジェクト作成（15秒版）
ad new 0101-バッグ査定-60s --from ~/Desktop/clip.mov --len 60   # 1分版（30秒版は --len 30）
# projects/0101-バッグ査定/brief.json に目的・CTA・目標秒数を書く
ad all 0101-バッグ査定          # カット案で止まる → 確認
ad approve 0101-バッグ査定
ad all 0101-バッグ査定          # カット→テロップ→書き出し→QA
```
- Claude Code（このフォルダで起動）: `/ad-edit <name>`、`/ad-qa <name>`
- Codex（このフォルダで起動）: 「kaitori-ad-style で <name> を15秒と30秒の2パターンで」
- 下書き確認だけなら `ad render <name> --draft`（速い）
- 演出を手で/AIで足すなら `npx hyperframes preview edit/hf`（ブラウザでプレビュー）

## 工程とツール
| 工程 | 中身 |
|---|---|
| 文字起こし | ElevenLabs Scribe（video-use 経由）。キー未設定ならローカル Whisper large-v3（無料・Metal で高速） |
| カット | 無音・フィラー（えーと等）・言い直しを自動判定 → **承認後に実行**。単語時刻を波形にスナップし、30ms フェード |
| リフレーム | 横素材も 1080×1920 に中央クロップ。iPhone HDR は SDR に変換 |
| テロップ | BudouX で文節改行、1行13字×2行、数字・価格・強調語を黄色、文節ごとポップイン、フックは上部に大きく |
| SE / 演出 | ポップ・キラ・シュッ（自作でライセンス問題なし）、強調時パンチインズーム、最後に CTA バナー |
| 音量 | 2パス loudnorm で -14 LUFS / TP -1.5 |
| QA | 仕様、1秒ごとのフレーム＋セーフゾーン枠のコンタクトシート、音量、再文字起こしとテロップの照合、景表法 NG 表現・表記ゆれ |

## 設定
- `brand/brand.json` — 色・フォント・寸法・セーフゾーン・強調語・**表記辞書(glossary)**・NG表現
- `brand/logo.png` — 置くと右上に表示
- `sfx/pop.* kira.* whoosh.*` — 置くと自作 SE の代わりに使う（効果音ラボ等、広告利用可のもの）
- `projects/<name>/brief.json` — 目標秒数、構成の目安、CTA、BGM（`"bgm": "bgm.mp3"`）、ズーム量など
- `templates/brief.json`（15秒）/ `brief-30s.json` / `brief-60s.json` — `ad new --len` で使う尺別の初期値

## ElevenLabs（任意・推奨）
日本語の精度を上げたい場合は、ElevenLabs の有料プランの API キーを自分で設定する:
```bash
open -e ~/Developer/video-use/.env   # ELEVENLABS_API_KEY=xxxxx と1行書いて保存
```
設定後は自動で Scribe が使われる（brief.json の `transcribe_engine` で `whisper` 固定も可）。

## 環境の再構築
```bash
bash tools/setup.sh
```
自動監視の停止/再開: `launchctl bootout gui/$(id -u)/com.hkobayashi.video-ad-inbox` / `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hkobayashi.video-ad-inbox.plist`

## 注意
- CapCut 内蔵音楽・非商用素材は広告に使わない。音声クローンは本人の書面同意を取る。
- 自動判定（言い直し・NG表現）は候補出し。訴求・表現の最終判断は人間。
