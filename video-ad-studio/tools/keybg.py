#!/usr/bin/env python3
"""グリーンバックの動画の緑を背景写真に差し替え、人物の色味をととのえる。

  python3 tools/keybg.py 入力.mp4 背景.png 出力.mp4 [--top 132] [--gain 1.05,1.0,0.94] [--sat 1.05] [--bright 1.03]

OpenCV と numpy が必要（tools/.keyenv の仮想環境で動かす）。入力は 1080×1920。音声は出力しない。
緑らしさ（G − max(R,B)）が高い所を背景にし、人物の縁に残る緑のにじみは抑えて背景色をなじませる。
"""
import argparse
import subprocess

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("bg"); ap.add_argument("dst")
ap.add_argument("--top", type=int, default=132)
ap.add_argument("--gain", default="1.05,1.0,0.94")      # R,G,B の倍率（肌を自然な暖かさに）
ap.add_argument("--sat", type=float, default=1.05)
ap.add_argument("--bright", type=float, default=1.03)
ap.add_argument("--gamma", type=float, default=1.0)    # 1未満で中間〜暗部を持ち上げる（暗い服・髪まで明るくする）
ap.add_argument("--shadow", type=float, default=0.0)   # 暗い部分（髪・服）の色みを抑える強さ 0〜1
ap.add_argument("--lo", type=float, default=7.0); ap.add_argument("--hi", type=float, default=20.0)
a = ap.parse_args()

import os
W, H = int(os.environ.get('AD_W', 1080)), int(os.environ.get('AD_H', 1920))
bg = cv2.imread(a.bg)
bg = cv2.resize(bg, (W, H)).astype(np.float32)
bgsoft = cv2.GaussianBlur(bg, (0, 0), 25)
gr, gg, gb = [float(x) for x in a.gain.split(",")]
gain = np.array([gb, gg, gr], np.float32)   # BGR

def process(fr):
    f = fr.astype(np.float32)
    B, G, R = f[..., 0], f[..., 1], f[..., 2]
    gs = G - np.maximum(R, B)
    al = 1 - np.clip((gs - a.lo) / (a.hi - a.lo), 0, 1)
    al[: a.top] = 0
    al = cv2.GaussianBlur(al, (0, 0), 1.0)
    # 緑のにじみを抑える
    f[..., 1] = np.minimum(G, np.maximum(R, B) + 4)
    # 縁（0<α<1）に背景色をなじませる
    edge = (al * (1 - al) * 4)[..., None]
    f = f * (1 - 0.35 * edge) + bgsoft * 0.35 * edge
    # 色味：暖かさ・彩度・明るさ
    f = f * gain * a.bright
    if a.gamma != 1.0:
        f = 255.0 * np.power(np.clip(f, 0, 255) / 255.0, a.gamma)
    gray = f.mean(2, keepdims=True)
    f = gray + (f - gray) * a.sat
    if a.shadow > 0:  # 暗い所ほど無彩色に寄せて、髪の青緑がかりを消す
        y = f.mean(2, keepdims=True)
        w = np.clip(np.clip((150 - y) / 150, 0, 1) * a.shadow, 0, 0.9)
        f = y + (f - y) * (1 - w)
    out = f * al[..., None] + bg * (1 - al[..., None])
    return np.clip(out, 0, 255).astype(np.uint8)

fps = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", a.src],
                     capture_output=True, text=True).stdout.strip().split(",")[0]
rd = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.src, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
wr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", fps, "-i", "-",
                       "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", a.dst], stdin=subprocess.PIPE)
n = W * H * 3
while True:
    b = rd.stdout.read(n)
    if len(b) < n:
        break
    wr.stdin.write(process(np.frombuffer(b, np.uint8).reshape(H, W, 3)).tobytes())
wr.stdin.close(); wr.wait(); rd.wait()
