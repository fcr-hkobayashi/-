#!/bin/bash
# inbox/ に置かれた動画を自動でプロジェクト化し、文字起こし→カット案まで進めて通知する。
# launchd（com.hkobayashi.video-ad-inbox）が inbox/ の変化を検知して起動する。
set -u
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin"
STUDIO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$STUDIO/inbox/.watch.log"
LOCK="$STUDIO/inbox/.lock"
mkdir "$LOCK" 2>/dev/null || exit 0          # 多重起動防止
trap 'rmdir "$LOCK"' EXIT
notify() { osascript -e "display notification \"$2\" with title \"動画広告スタジオ\" subtitle \"$1\"" >/dev/null 2>&1; }

shopt -s nullglob nocaseglob
for f in "$STUDIO"/inbox/*.{mp4,mov,m4v,mkv,webm}; do
  # コピー途中のファイルを避ける：10秒間サイズが変わらなくなるまで待つ
  s1=$(stat -f%z "$f"); sleep 10; s2=$(stat -f%z "$f")
  [ "$s1" = "$s2" ] || continue
  base="$(basename "${f%.*}" | tr ' /' '__')"
  name="$(date +%Y%m%d)-${base}"
  # ファイル名に 60s / 1分 / 30s が入っていれば、その尺のテンプレートを使う
  len=15
  case "$base" in *60s*|*1分*|*60秒*) len=60 ;; *30s*|*30秒*) len=30 ;; esac
  {
    echo "=== $(date '+%F %T') $f → $name"
    "$STUDIO/bin/ad" new "$name" --from "$f" --move --len "$len" &&
    "$STUDIO/bin/ad" transcribe "$name" &&
    "$STUDIO/bin/ad" plan "$name" >/dev/null &&
    notify "$name" "カット案ができました。edit/cut_plan.md を確認して承認してください" ||
    notify "$name" "処理に失敗しました（inbox/.watch.log）"
  } >>"$LOG" 2>&1
done
