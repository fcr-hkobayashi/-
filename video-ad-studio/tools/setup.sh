#!/bin/bash
# video-ad-studio の環境を（再）構築する。何度実行しても安全。
set -euo pipefail
STUDIO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$STUDIO"
echo "▶ Homebrew パッケージ"; brew install ffmpeg uv yt-dlp whisper-cpp node >/dev/null
echo "▶ video-use"; test -d ~/Developer/video-use || git clone https://github.com/browser-use/video-use ~/Developer/video-use
(cd ~/Developer/video-use && git pull --ff-only -q && uv sync -q)
echo "▶ HyperFrames / BudouX"; npm install --silent; uv sync -q
npx hyperframes browser ensure >/dev/null
echo "▶ スキル登録（Claude Code / Codex）"
mkdir -p ~/.claude/skills ~/.codex/skills ~/.agents/skills
for d in ~/.claude/skills ~/.codex/skills; do ln -sfn ~/Developer/video-use "$d/video-use"; done
for d in ~/.claude/skills ~/.codex/skills ~/.agents/skills; do ln -sfn "$STUDIO/skills/kaitori-ad-style" "$d/kaitori-ad-style"; done
npx hyperframes skills update >/dev/null 2>&1 || npx hyperframes skills >/dev/null
echo "▶ フォント"; cp fonts/*.ttf ~/Library/Fonts/
echo "▶ Whisper モデル（約3GB・初回のみ）"
M=~/.cache/hyperframes/whisper/models/ggml-large-v3.bin
test -f "$M" || { mkdir -p "$(dirname "$M")"; curl -L -o "$M" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin; }
ln -sfn "$STUDIO/bin/ad" /opt/homebrew/bin/ad
echo "▶ ElevenLabs キー: $(grep -q '^ELEVENLABS_API_KEY=..' ~/Developer/video-use/.env 2>/dev/null && echo 設定済み || echo '未設定（ローカルWhisperで動作）')"
echo "▶ inbox 自動監視（launchd）"
PL=~/Library/LaunchAgents/com.hkobayashi.video-ad-inbox.plist
cat > "$PL" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.hkobayashi.video-ad-inbox</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$STUDIO/tools/inbox_watch.sh</string></array>
  <key>WatchPaths</key><array><string>$STUDIO/inbox</string></array>
  <key>ProcessType</key><string>Interactive</string>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>/tmp/video-ad-inbox.out</string>
  <key>StandardErrorPath</key><string>/tmp/video-ad-inbox.err</string>
</dict></plist>
PLIST
launchctl bootout gui/$(id -u)/com.hkobayashi.video-ad-inbox 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PL"
echo "✅ 完了"
