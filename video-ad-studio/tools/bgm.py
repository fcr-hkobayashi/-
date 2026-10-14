#!/usr/bin/env python3
"""書き出した動画に BGM を入れる（声の後ろで小さく流し、声が出ている間は自動で下げる）。

  python3 tools/bgm.py <project> <動画ファイル名> <BGMファイル> --suffix _冒頭1_BGM [--target -30]

- 曲の音量を測って、声の後ろで target LUFS 前後になるよう下げる（Cr01/03/05 は -30、Cr02 は -33＋後半+0.41）
- 曲が動画より短ければ、つなぎ目を xfade 秒重ねて繰り返す
- 声とのダッキング（sidechaincompress）→ 全体を -14 LUFS にそろえて output に保存
"""
from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ad  # noqa: E402


def lufs(f: Path) -> float:
    o = subprocess.run(["ffmpeg", "-v", "info", "-i", str(f), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[0-9.]+) LUFS", o)[-1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("video", help="output/ の中の動画ファイル名")
    ap.add_argument("bgm", help="BGM ファイル（プロジェクトからの相対パス可）")
    ap.add_argument("--suffix", required=True)
    ap.add_argument("--target", type=float, default=-30.0, help="声の後ろでの BGM の大きさ（LUFS）")
    ap.add_argument("--duck-ratio", type=float, default=5.0, help="声が出ている間に BGM を下げる強さ（大きいほど下がる。2〜3で控えめ）")
    ap.add_argument("--fade-in", type=float, default=0.8)
    ap.add_argument("--fade-out", type=float, default=1.7)
    ap.add_argument("--xfade", type=float, default=1.0, help="曲を繰り返すときに重ねる秒")
    ap.add_argument("--ramp-at", type=float, default=None, help="この秒から BGM を少し上げる（Cr02 で使用）")
    ap.add_argument("--ramp", type=float, default=0.41)
    a = ap.parse_args()
    p = ad.Project(a.project)
    video = p.output / a.video
    bgm = Path(a.bgm) if Path(a.bgm).is_absolute() else p.dir / a.bgm
    dur, bdur = ad.ffprobe_duration(video), ad.ffprobe_duration(bgm)
    n = max(1, math.ceil((dur + 0.5) / max(1.0, bdur - a.xfade)))
    g = a.target - lufs(bgm)
    ins = sum([["-i", bgm] for _ in range(n)], [])
    chain = "[1:a]" if n == 1 else ""
    if n > 1:
        prev = "[1:a]"
        for k in range(2, n + 1):
            out = f"[x{k}]" if k < n else ""
            chain += f"{prev}[{k}:a]acrossfade=d={a.xfade}:c1=tri:c2=tri{out}" + (";" if k < n else "")
            prev = out
        chain += ","
    else:
        chain = "[1:a]"
    ramp = (f"volume=eval=frame:volume='1+{a.ramp}*min(max((t-{a.ramp_at})/1.5\\,0)\\,1)',"
            if a.ramp_at is not None else "")
    fc = (f"{chain}aresample=48000,aformat=channel_layouts=stereo,volume={g:.1f}dB,{ramp}"
          f"afade=t=in:d={a.fade_in},afade=t=out:st={dur - a.fade_out - 0.1:.2f}:d={a.fade_out},atrim=0:{dur:.3f}[bgm];"
          f"[0:a]aresample=48000,asplit=2[v1][v2];"
          f"[bgm][v2]sidechaincompress=threshold=0.025:ratio={a.duck_ratio}:attack=25:release=380:makeup=1[duck];"
          f"[v1][duck]amix=inputs=2:normalize=0:duration=first[out]")
    raw = p.edit / f"mix{a.suffix}.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", video, *ins, "-filter_complex", fc, "-map", "0:v", "-map", "[out]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", raw])
    final = ad.loudnorm_to_output(p, raw, suffix=a.suffix)
    ad.log(f"BGM {bgm.name}（{n}回つなぎ・{g:+.1f}dB）→ {final.relative_to(ad.STUDIO)}")


if __name__ == "__main__":
    main()
