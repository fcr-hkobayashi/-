#!/usr/bin/env python3
"""手持ち映像のカメラの動きを打ち消して「固定」する（背景の特徴点を追い、手など動くものは外れ値として無視）。

  python3 tools/stabilize.py 入力.mp4 出力.mp4 [--sigma 0=完全固定 / 数字=ゆるやかに追従(フレーム数)] [--zoom 1.2]

入力は 1080×1920 の SDR 動画（ugc.py の edit/sdr/ にできるもの）を想定。出力は音声なし。
"""
import argparse
import subprocess

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--sigma", type=float, default=0.0)
ap.add_argument("--zoom", type=float, default=1.0)
a = ap.parse_args()

cap = cv2.VideoCapture(a.src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frames = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    frames.append(f)
n, (h, w) = len(frames), frames[0].shape[:2]
grays = [cv2.cvtColor(cv2.resize(f, None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY) for f in frames]

# 前のコマ→次のコマの動き（拡大縮小・回転・平行移動）を求めて足し合わせる
M = [np.eye(3)]
for i in range(1, n):
    p0 = cv2.goodFeaturesToTrack(grays[i - 1], 600, 0.01, 12)
    p1, st, _ = cv2.calcOpticalFlowPyrLK(grays[i - 1], grays[i], p0, None)
    ok = st.ravel() == 1
    m, _ = cv2.estimateAffinePartial2D(p1[ok], p0[ok], method=cv2.RANSAC, ransacReprojThreshold=2.0)
    T = np.eye(3)
    if m is not None:
        T[:2] = m
        T[:2, 2] *= 2  # 半分の大きさで測ったので戻す
    M.append(M[-1] @ T)  # 「いまのコマ → 最初のコマ」への変換

if a.sigma > 0:  # ゆるやかに追従：動きの軌跡をぼかす
    path = np.array([np.linalg.inv(m) for m in M])  # 最初→いまのコマ
    k = int(a.sigma * 3)
    wts = np.exp(-0.5 * (np.arange(-k, k + 1) / a.sigma) ** 2)
    sm = []
    for i in range(n):
        idx = np.clip(np.arange(i - k, i + k + 1), 0, n - 1)
        sm.append(np.tensordot(wts / wts.sum(), path[idx], axes=1))
    M = [np.linalg.inv(s) @ np.linalg.inv(m) @ np.eye(3) for s, m in zip(sm, M)]
    M = [np.linalg.inv(np.linalg.inv(m)) for m in M]

tx = [m[0, 2] for m in M]; ty = [m[1, 2] for m in M]
print(f"動き: 横 {min(tx):.0f}〜{max(tx):.0f}px / 縦 {min(ty):.0f}〜{max(ty):.0f}px / {n}コマ")

c = np.array([[a.zoom, 0, w * (1 - a.zoom) / 2], [0, a.zoom, h * (1 - a.zoom) / 2], [0, 0, 1]])
enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
                        "-i", "-", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", a.dst], stdin=subprocess.PIPE)
for f, m in zip(frames, M):
    out = cv2.warpAffine(f, (c @ m)[:2], (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    enc.stdin.write(out.tobytes())
enc.stdin.close(); enc.wait()
