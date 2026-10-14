#!/usr/bin/env python3
"""ugc.py で書き出した動画（声だけ）に、仕上げの処理を順にかける。Cr03 で確立した手順。

  python3 tools/ugc_post.py <project> --variant 冒頭1 --speed 1.15 --bgm assets/bgm/quality_of_life.mp3 --bgm-target -22 --out Cr3_冒頭1_仕上げ.mp4

1. 声の大きさを区間ごとにそろえる（小さい区間は上げ、大きすぎる区間は下げる）
2. 声に共通の処理（ノイズ除去・圧縮・軽い音色調整）＋ 常時ルームトーン（無音の質をそろえる）＋ つなぎ目をなだらかに
3. 速さを変える（--speed）
4. 効果音（tools/sfx_mix.py のルール）
5. BGM（tools/bgm.py）
どれかが失敗したら、そこで止まる（古いファイルのまま先に進まない）。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

STUDIO = Path(__file__).resolve().parent.parent


def run(cmd: list, **kw):
    r = subprocess.run([str(c) for c in cmd], **kw)
    if r.returncode != 0:
        sys.exit(f"失敗: {' '.join(str(c) for c in cmd[:3])}")
    return r


def pcm(f: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(f), "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(float) / 32768


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--variant", required=True)
    ap.add_argument("--speed", type=float, default=1.25)
    ap.add_argument("--bgm", default="assets/bgm/quality_of_life.mp3")
    ap.add_argument("--bgm-target", type=float, default=-25.0)
    ap.add_argument("--xfade", type=float, default=3.5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--room-tone", type=float, default=0.02, help="ルームトーンの振幅（0.02 ≒ -50dB）")
    a = ap.parse_args()
    P = STUDIO / "projects" / a.project
    O = P / "output"
    tl = json.loads((P / "edit" / f"ugc_{a.variant}" / "timeline.json").read_text(encoding="utf-8"))
    src = Path(max(glob.glob(str(O / f"{a.project}_{a.variant}_[0-9]*s.mp4")), key=os.path.getmtime))
    print("入力:", src.name)

    # 1) 声の大きさをそろえる
    x, sr = pcm(src), 16000
    lv = []
    for s in tl:
        seg = x[int(s["at"] * sr): int((s["at"] + s["len"]) * sr)]
        fr = seg[: len(seg) // 320 * 320].reshape(-1, 320)
        r = np.sqrt((fr ** 2).mean(1))
        sp = r[r > 0.02] if (r > 0.02).sum() > 5 else r
        lv.append(20 * np.log10(np.sqrt((sp ** 2).mean()) + 1e-9))
    target = float(np.median(lv)) + 0.5
    chain = []
    for s, l in zip(tl, lv):
        g = max(-3.0, min(5.0, target - l))
        if abs(g) >= 0.6:
            chain.append(f"volume={g:.2f}dB:enable='between(t,{s['at']:.3f},{s['at'] + s['len']:.3f})'")
    g_out = O / f"{a.project}_post_G.mp4"
    af = ",".join(chain + ["alimiter=limit=0.89:level=disabled"])
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", g_out])
    print(f"1) 声の大きさ：目標 {target:.1f} dB に {len(chain)} 区間を調整")

    # 2) 共通処理＋ルームトーン＋つなぎ目
    bs = sorted({round(s["at"], 3) for s in tl[1:]})
    dip = "*".join(f"(0.55+0.45*min(1,abs(t-{b})/0.014))" for b in bs)
    voice = ("[0:a]highpass=f=70,afftdn=nr=9:nf=-48:tn=0,"
             "acompressor=threshold=-24dB:ratio=2.2:attack=8:release=140:makeup=2,"
             "equalizer=f=250:t=q:w=1.2:g=-1.2,equalizer=f=3200:t=q:w=1.0:g=1.0,"
             f"volume='{dip}':eval=frame,alimiter=limit=0.9:level=disabled,aresample=48000,aformat=channel_layouts=stereo[v];")
    tone = (f"anoisesrc=color=pink:amplitude={a.room_tone}:sample_rate=48000:seed=7,lowpass=f=5000,highpass=f=90,"
            "aformat=channel_layouts=stereo[rt];")
    v_out = O / f"{a.project}_post_V.mp4"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", g_out, "-filter_complex",
         voice + tone + "[v][rt]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", v_out])
    print("2) 共通処理・ルームトーン・つなぎ目：完了")

    # 3) 速さ
    sp_out = O / f"{a.project}_post_speed.mp4"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", v_out, "-filter_complex",
         f"[0:v]setpts=PTS/{a.speed}[v];[0:a]atempo={a.speed}[a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
         "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", sp_out])
    print(f"3) {a.speed} 倍速：完了")

    # 4) 効果音  5) BGM
    run([sys.executable, STUDIO / "tools/sfx_mix.py", a.project, sp_out.name, "--variant", a.variant,
         "--speed", str(a.speed), "--suffix", "_sfx"], stdout=subprocess.DEVNULL)
    sfx = Path(sp_out.stem + "_sfx.mp4")
    print("4) 効果音：完了")
    run([sys.executable, STUDIO / "tools/bgm.py", a.project, sfx.name, a.bgm, "--suffix", "_post",
         "--target", str(a.bgm_target), "--fade-in", "0.6", "--xfade", str(a.xfade)], stdout=subprocess.DEVNULL)
    made = Path(max(glob.glob(str(O / f"{a.project}_post_[0-9]*s.mp4")), key=os.path.getmtime))
    out = O / a.out
    out.write_bytes(made.read_bytes())
    print("5) BGM：完了 →", out.relative_to(STUDIO))


if __name__ == "__main__":
    main()
