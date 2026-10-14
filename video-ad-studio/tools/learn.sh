#!/bin/bash
# 参考動画を「学習素材」として取り込む：URL（X/YouTube等）またはローカルファイル → references/learn/<slug>/
#   video.mp4 / meta.json / transcript.txt / frames/（5秒毎）/ contact.jpg
# 取り込んだ後、Claude が内容を読んで references/LEARNED.md に要点を追記する（/learn-ref）。
# 使い方: tools/learn.sh <URL|ファイル> [スラッグ]
set -eu
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin"
STUDIO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$1"; SLUG="${2:-$(date +%Y%m%d)-$(echo "$SRC" | md5 -q | cut -c1-6)}"
D="$STUDIO/references/learn/$SLUG"; mkdir -p "$D/frames"
if [ -f "$SRC" ]; then cp "$SRC" "$D/video.mp4"
else yt-dlp -q --no-progress -f "bv*+ba/b" --merge-output-format mp4 --write-info-json \
       -o "$D/video.%(ext)s" "$SRC"; mv "$D"/video.info.json "$D/meta.json" 2>/dev/null || true
fi
ffmpeg -v error -y -i "$D/video.mp4" -ar 16000 -ac 1 "$D/audio.wav"
MODEL="${WHISPER_MODEL:-$HOME/.cache/hyperframes/whisper/models/ggml-large-v3.bin}"
whisper-cli -m "$MODEL" -f "$D/audio.wav" -l ja -otxt -of "$D/transcript" -t 8 >/dev/null 2>&1
ffmpeg -v error -y -i "$D/video.mp4" -vf "fps=1/5,scale=640:-2" "$D/frames/f_%04d.jpg"
ffmpeg -v error -y -i "$D/video.mp4" -vf "fps=1/10,scale=320:-2,tile=6x6" -frames:v 1 "$D/contact.jpg"
rm -f "$D/audio.wav"; echo "$D"
