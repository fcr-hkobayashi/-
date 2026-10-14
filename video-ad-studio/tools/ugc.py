#!/usr/bin/env python3
"""つぎはぎ型（参考：CR12b）を edit.json から組み立てる。指定の映像範囲に、別録り音声を口に合わせて当てる。

  python3 tools/ugc.py <name> [--variant 冒頭1] [--draft]

edit.json の segments（上から順につなぐ）:
- src: sources のキー（映像）
- v: [[開始, 終了], ...]  使う映像範囲（ユーザー指定の秒）。複数ならつなぐ。
     snap（既定 true）：範囲の端が言葉の途中なら言葉の切れ目まで広げ、前後の無音は詰める
- audio: {"file", "start", "end", "warp"}
    - warp: true … 映像側（撮影時の音）と同じ文字の時刻に合わせて、音声を区切りごとに伸縮して口に合わせる
    - warp なし … そのまま乗せる（口の映らない Bロール）。映像は音声の長さに合わせる（足りなければゆっくり再生）
- lock（既定 true・人物の映像）：頭の位置を全カットで同じ場所にそろえる
- style: talk.py と同じ（hook / yellow / red / mono / tate / cta / card）に加えて split（上に映像・下に黒地と白文字）
- telop: '|' で次のテロップ、'/' で改行、*語* 黄、#語# 大きい黄、!語! 赤
テロップの見た目は CR25 型（talk.compose）を使う。右上に肩書き（title_badge）。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import subprocess
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ad  # noqa: E402
import talk  # noqa: E402

W, H, FPS = ad.W, ad.H, ad.FPS
LOCK_ZOOM = 1.10          # 頭の位置合わせ用に少し拡大（はみ出し分でずらす）
HEAD_TOP, HEAD_X = 0.20, 0.5   # そろえる位置：頭頂を画面上から20%、頭の中心を左右中央


def frames(t: float) -> float:
    return round(round(t * FPS) / FPS, 4)


def sdr(p: ad.Project, src: Path, a: float, dur: float) -> Path:
    """iPhone の HDR を avconvert で SDR・縦向き（1080×1920）に。区間ごとにキャッシュ。"""
    cache = p.edit / "sdr"
    cache.mkdir(exist_ok=True)
    if src.stem.startswith("pre_"):  # 仕上げ済み（1080×1920・SDR）の動画はそのまま切り出す
        out = cache / f"{src.stem}_{a:.2f}_{dur:.2f}.mp4"
        if not out.exists():
            ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-i", src, "-t", f"{dur + 0.3:.3f}", "-an",
                    "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out])
        return out
    if src.suffix.lower() in (".jpg", ".jpeg", ".png"):  # 静止画：縦長に切り出し済みの画像を、ゆっくりズームする短い動画にする
        out = cache / f"{src.stem}_img_{a:.2f}_{dur:.2f}.mp4"
        if not out.exists():
            n = int((dur + 0.3) * FPS) + 1
            ad.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", src, "-vf",
                    f"scale={W * 2}:{H * 2},zoompan=z='1+0.06*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},format=yuv420p",
                    "-frames:v", str(n), "-c:v", "libx264", "-crf", "16", out])
        return out
    out = cache / f"{src.stem}_{a:.2f}_{dur:.2f}.mp4"
    if not out.exists() or ad.ffprobe_duration(out) < dur - 0.1:
        w = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                            "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
        preset = "Preset3840x2160" if w == "3840" else "Preset1920x1080"
        ad.run(["avconvert", "-s", src, "-o", out, "-p", preset, "--start", f"{a:.3f}",
                "--duration", f"{dur + 0.3:.3f}", "--replace"], stdout=subprocess.DEVNULL)
    return out


def silences(f: Path, a: float, b: float) -> list[tuple[float, float]]:
    o = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(f), "-map", "0:a:0",
                        "-af", "silencedetect=n=-40dB:d=0.12", "-f", "null", "-"], capture_output=True, text=True).stderr
    ev = [(k, float(v) + a) for k, v in re.findall(r"silence_(start|end): ([0-9.]+)", o)]
    out, st = [], None
    for k, t in ev:
        if k == "start":
            st = t
        elif st is not None:
            out.append((st, t))
            st = None
    if st is not None:
        out.append((st, b))
    return out


def snap(f: Path, a: float, b: float) -> tuple[float, float]:
    """範囲の端を言葉の切れ目に合わせる：言葉の途中なら広げ（最大0.8秒）、無音なら詰める。"""
    sil = silences(f, max(0.0, a - 0.9), b + 0.9)
    def in_sil(t):
        return next(((x, y) for x, y in sil if x <= t <= y), None)
    s = in_sil(a)
    if s:
        a2 = min(b - 0.3, s[1] - 0.08)
    else:
        prev = [y for x, y in sil if y <= a]
        a2 = max(a - 0.8, (prev[-1] - 0.08) if prev else a - 0.8)
    s = in_sil(b)
    if s:
        b2 = max(a2 + 0.3, s[0] + 0.12)
    else:
        nxt = [x for x, y in sil if x >= b]
        b2 = min(b + 0.8, (nxt[0] + 0.12) if nxt else b + 0.8)
    return round(a2, 3), round(b2, 3)


def head(clip: Path) -> tuple[float, float]:
    """明るい壁の前の黒髪から、頭頂の高さと頭の左右中心を測る（画面に対する割合）。"""
    w, h = 270, 480
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.1", "-i", str(clip), "-frames:v", "1", "-vf",
                          f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    import numpy as np
    g = np.frombuffer(raw, np.uint8).reshape(h, w)
    dark = g[: int(h * 0.6), int(w * 0.15): int(w * 0.85)] < 70
    rows = dark.sum(1)
    top = int(np.argmax(rows > 10))
    band = dark[top: top + 50]
    xs = np.where(band)[1]
    cx = (xs.mean() + int(w * 0.15)) / w if len(xs) else 0.5
    return top / h, float(cx)


def feats(wav: Path):
    """16kHz の音声から 20ms ごとの対数メル風スペクトル（帯ごとに正規化）。DTW 用。"""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-af",
                          "highpass=f=80", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    hop, n = 320, 640
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    sp = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    edges = np.geomspace(4, sp.shape[1] - 1, 25).astype(int)
    mel = np.stack([sp[:, edges[k]:edges[k + 1] + 1].sum(1) for k in range(24)], axis=1)
    lm = np.log(mel + 1e-8)
    energy = lm.max(1)
    lm = (lm - lm.mean(0)) / (lm.std(0) + 1e-6)
    return lm, energy


def speech_span(wav: Path, thr: float = -38.0) -> tuple[float, float]:
    """16kHz モノラル音声の、声が出ている最初と最後の秒（10ms ごとの音量 thr dB 超え）。"""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = 160
    db = np.array([20 * np.log10(np.sqrt((x[i:i + n] ** 2).mean()) + 1e-9) for i in range(0, max(n, len(x) - n), n)])
    act = np.where(db > thr)[0]
    return (act[0] * 0.01, (act[-1] + 1) * 0.01) if len(act) else (0.0, len(x) / 16000)


def dtw_map(audio_wav: Path, cam_wav: Path) -> tuple[list[tuple[float, float]], float, float]:
    """別録り音声（全体）を撮影時の音の中の一部に重ねる部分列 DTW。
    戻り値：(音声秒, 映像秒) の対応点、映像側の一致の始まりと終わり。"""
    import numpy as np
    A, ea = feats(audio_wav)
    B, eb = feats(cam_wav)
    na, nb = len(A), len(B)
    C = 1 - (A @ B.T) / (np.linalg.norm(A, axis=1)[:, None] * np.linalg.norm(B, axis=1)[None, :] + 1e-6)
    D = np.full((na, nb), np.inf)
    D[0] = C[0]
    for i in range(1, na):
        prev = D[i - 1]
        best = np.minimum(prev, np.concatenate([[np.inf], prev[:-1]]))
        row = C[i] + best
        # 横方向（映像側だけ進む＝音声の1コマを伸ばす）は累積で
        for j in range(1, nb):
            v = row[j - 1] + C[i, j] * 1.0
            if v < row[j]:
                row[j] = v
        D[i] = row
    j = int(np.argmin(D[-1]))
    path = [(na - 1, j)]
    i = na - 1
    while i > 0:
        cands = [(D[i - 1, j], i - 1, j)]
        if j > 0:
            cands += [(D[i - 1, j - 1], i - 1, j - 1), (D[i, j - 1], i, j - 1)]
        _, i, j = min(cands)
        path.append((i, j))
    path.reverse()
    hop = 0.02
    pts = [(ia * hop, jb * hop) for ia, jb in path]
    return pts, pts[0][1], pts[-1][1]


def words_of(wav: Path) -> tuple[str, list[float]]:
    ws = ad.transcribe_whisper(wav, wav.with_suffix(".whisper.json"))
    return ad.char_times(ws) if ws else ("", [])


def warp_audio(p: ad.Project, work: Path, au: dict, cam: Path, length: float, out: Path) -> None:
    """別録り音声を、映像側の撮影時の音（cam）の同じ文字の時刻に合わせて区切りごとに伸縮する。"""
    a, b = au["start"], au["end"]
    wa = work / f"{out.stem}_a.wav"
    ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", p.dir / au["file"],
            "-ac", "1", "-ar", "16000", wa])
    ta, tia = words_of(wa)
    tv, tiv = words_of(cam)
    na, nv = [ad.norm(c) for c in ta], [ad.norm(c) for c in tv]
    # 先頭：撮影時の音の最初の文字と、別録り音声の最初の文字をそろえる
    anchors = [(0.0, 0.0)]
    if tia and tiv:
        lead_a, lead_v = tia[0], tiv[0]
        if lead_v > lead_a:
            anchors = [(0.0, lead_v - lead_a)]
    for blk in difflib.SequenceMatcher(None, na, nv, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            x, y = tia[blk.a + k], tiv[blk.b + k]
            if x - anchors[-1][0] >= 0.25 and y - anchors[-1][1] >= 0.25:
                r = (x - anchors[-1][0]) / (y - anchors[-1][1])
                if 0.75 <= r <= 1.33:
                    anchors.append((x, y))
    end_v = min(length, anchors[-1][1] + (b - a - anchors[-1][0]) * 1.0)
    anchors.append((b - a, max(anchors[-1][1] + 0.1, end_v)))
    fc, labels = "", []
    if anchors[0][1] > 0:
        fc += f"anullsrc=r=48000:cl=mono,atrim=0:{anchors[0][1]:.4f}[s];"
        labels.append("[s]")
    for k in range(len(anchors) - 1):
        (x0, y0), (x1, y1) = anchors[k], anchors[k + 1]
        tempo = max(0.6, min(1.6, (x1 - x0) / max(0.05, y1 - y0)))
        fc += f"[0:a]atrim={a + x0:.4f}:{a + x1:.4f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=mono,atempo={tempo:.4f}[p{k}];"
        labels.append(f"[p{k}]")
    fc += "".join(labels) + f"concat=n={len(labels)}:v=0:a=1,apad,atrim=0:{length:.4f}[a]"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", p.dir / au["file"], "-filter_complex", fc, "-map", "[a]",
            "-ar", "48000", "-ac", "2", out])
    ad.save_json(out.with_suffix(".anchors.json"), anchors)


def stretch(p: ad.Project, au: dict, anchors: list, length: float, out: Path) -> None:
    """対応点ごとに音声を区切って伸縮し、映像の口の動きの時刻に並べる。"""
    a = au["start"]
    fc, labels = "", []
    if anchors[0][1] > 0.005:
        fc += f"anullsrc=r=48000:cl=mono,atrim=0:{anchors[0][1]:.4f}[s];"
        labels.append("[s]")
    for k in range(len(anchors) - 1):
        (x0, y0), (x1, y1) = anchors[k], anchors[k + 1]
        if x1 - x0 < 0.01:
            continue
        want = (x1 - x0) / max(0.02, y1 - y0)
        tempo = max(0.55, min(1.8, want))
        # 伸ばしきれない区切り（間など）は無音で埋めて、次の区切りの頭がずれないようにする
        fill = f",apad,atrim=0:{y1 - y0:.4f}" if want < 0.55 else ""
        fc += (f"[0:a]atrim={a + x0:.4f}:{a + x1:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
               f"aformat=channel_layouts=mono,atempo={tempo:.4f}{fill}[p{k}];")
        labels.append(f"[p{k}]")
    fc += "".join(labels) + f"concat=n={len(labels)}:v=0:a=1,afade=t=in:d=0.02,apad,atrim=0:{length:.4f}[a]"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", p.dir / au["file"], "-filter_complex", fc, "-map", "[a]",
            "-ar", "48000", "-ac", "2", out])


def env_corr(src: Path, a: float, b: float, wav: Path) -> float:
    """撮影時の音（口の動きの目安）と、当てた音声の音量の動きの相関。"""
    import numpy as np
    def env(cmd):
        x = np.abs(np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.int16).astype(np.float32))
        x = np.convolve(x, np.ones(30) / 30, "same")
        return x / (x.max() + 1e-6)
    c = env(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src), "-map", "0:a:0",
             "-ac", "1", "-ar", "1000", "-f", "s16le", "-"])
    u = env(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "1000", "-f", "s16le", "-"])
    n = min(len(c), len(u))
    return float(np.corrcoef(c[:n], u[:n])[0, 1]) if n > 50 else -1.0


def onset(f: Path, a: float | None = None, b: float | None = None) -> float:
    """声が鳴り始める時刻（区間の頭からの秒）。"""
    cmd = ["ffmpeg", "-v", "info"] + (["-ss", f"{a:.3f}", "-to", f"{b:.3f}"] if a is not None else []) + \
        ["-i", str(f), "-map", "0:a:0", "-af", "silencedetect=n=-40dB:d=0.08", "-f", "null", "-"]
    o = subprocess.run(cmd, capture_output=True, text=True).stderr
    ev = [(k, float(v)) for k, v in re.findall(r"silence_(start|end): ([0-9.]+)", o)]
    if ev and ev[0][0] == "start" and ev[0][1] < 0.03:
        return next((t for k, t in ev if k == "end"), 0.0)
    return 0.0


def align_onset(cam_src: Path, a: float, b: float, wav: Path, dur: float) -> float:
    """話し始めを撮影時の音にそろえる（口が動き出す時刻に声の頭を合わせる）。ずらした秒を返す。"""
    d = onset(cam_src, a, b) - onset(wav)
    if abs(d) < 0.04:
        return 0.0
    tmp = wav.with_name(wav.stem + "_on.wav")
    af = (f"adelay={int(d * 1000)}:all=1" if d > 0 else f"atrim=start={-d:.4f},asetpts=PTS-STARTPTS") + \
        f",apad,atrim=0:{dur:.4f}"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-af", af, "-ar", "48000", "-ac", "2", tmp])
    tmp.replace(wav)
    return round(d, 3)


def build(p: ad.Project, spec: dict, work: Path) -> list[dict]:
    srcs = {k: p.dir / v for k, v in spec["sources"].items()}
    # 1) 範囲を確定（言葉の切れ目に合わせる）
    plan, anchors_of, cleans = [], {}, {}
    adir = work / "align"
    adir.mkdir(exist_ok=True)
    for i, s in enumerate(spec["segments"]):
        src = srcs[s["src"]]
        rngs = [list(r) for r in s["v"]]
        au = s.get("audio") or {}
        if au.get("warp") and s.get("anchors"):
            # 手で決めた対応点（[音声の秒, 映像の秒], ...）。映像の秒は元動画の時刻。複数範囲はつないだ後の時刻に直す
            def rel(t):
                acc = 0.0
                for ra, rb in rngs:
                    if ra - 0.05 <= t <= rb + 0.05:
                        return acc + min(max(t, ra), rb) - ra
                    acc += rb - ra
                raise ValueError(f"対応点 {t} が映像範囲の外です")
            pts = sorted(s["anchors"])
            a0, a1 = pts[0][0], pts[-1][0]
            raw48 = adir / f"{i:02d}_raw.wav"
            ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a0:.3f}", "-to", f"{a1:.3f}", "-i", p.dir / au["file"],
                    "-ac", "1", "-ar", "48000", raw48])
            anchors_of[i] = [(x - a0, rel(y)) for x, y in pts]
            cleans[i] = {"file": str(raw48), "start": 0.0, "end": a1 - a0, "warp": True}
            ad.save_json(adir / f"{i:02d}.json", {"range": rngs, "how": "manual", "anchors": anchors_of[i]})
        elif au.get("warp"):
            # 指定範囲（前後0.4秒の余裕つき）の撮影時の音の中から、台詞と同じ響きの部分を DTW で探す
            a, b = rngs[0][0], rngs[-1][1]
            pad = s.get("pad", 0.4)
            ca, cb = max(0.0, a - pad), b + pad
            cam, aw = adir / f"{i:02d}_cam.wav", adir / f"{i:02d}_aud.wav"
            ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ca:.3f}", "-to", f"{cb:.3f}", "-i", src, "-map", "0:a:0",
                    "-ac", "1", "-ar", "16000", cam])
            # 別録り音声そのまま／文中の長い間（0.25秒超）を詰めたもの の2通りで合わせ、口の動きとよく合う方を使う
            raw48, clean = adir / f"{i:02d}_raw.wav", adir / f"{i:02d}_clean.wav"
            ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{au['start']:.3f}", "-to", f"{au['end']:.3f}", "-i",
                    p.dir / au["file"], "-ac", "1", "-ar", "48000", raw48])
            ad.run(["ffmpeg", "-y", "-v", "error", "-i", raw48, "-af",
                    "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.03:"
                    "stop_periods=-1:stop_duration=0.25:stop_threshold=-40dB:stop_silence=0.12", clean])
            best = None
            for name, f in (("raw", raw48), ("clean", clean)):
                ad.run(["ffmpeg", "-y", "-v", "error", "-i", f, "-ar", "16000", aw])
                cau = {"file": str(f), "start": 0.0, "end": ad.ffprobe_duration(f), "warp": True}
                pts, ms, me = dtw_map(aw, cam)
                va, vb = ca + max(0.0, ms - 0.10), min(cb, ca + me + 0.18)
                anc, last = [(0.0, ms - (va - ca))], (0.0, ms - (va - ca))
                for x, y in pts:
                    y2 = y - (va - ca)
                    if x - last[0] >= 0.2 and y2 - last[1] >= 0.1 and 0.6 <= (x - last[0]) / (y2 - last[1]) <= 1.6:
                        anc.append((x, y2))
                        last = (x, y2)
                anc.append((cau["end"], max(last[1] + 0.05, me - (va - ca))))
                test = adir / f"{i:02d}_{name}_test.wav"
                stretch(p, cau, anc, vb - va, test)
                score = env_corr(src, va, vb, test)
                if best is None or score > best[0]:
                    best = (score, name, cau, anc, va, vb, ms, me)
            score, name, au, anc, va, vb, ms, me = best
            if s.get("keep"):  # 指定範囲をそのまま使う（対応点を範囲の頭からの時刻に直す）
                shift = va - a
                va, vb = a, b
                anc = [(x, y + shift) for x, y in anc]
            rngs = [[round(va, 3), round(vb, 3)]]
            anchors_of[i] = anc
            cleans[i] = au
            ad.save_json(adir / f"{i:02d}.json", {"range": rngs, "match": [ms, me], "how": name,
                                                  "score": round(score, 3), "anchors": anc})
        plan.append(rngs)
    # 2) 頭の位置（人物の映像だけ）
    heads = {}
    for i, s in enumerate(spec["segments"]):
        if s.get("lock", bool(s.get("audio", {}).get("warp"))):
            for k, (a, b) in enumerate(plan[i]):
                heads[(i, k)] = head(sdr(p, srcs[s["src"]], a, b - a))
    ad.save_json(work / "heads.json", {f"{i}_{k}": v for (i, k), v in heads.items()})
    segs, t = [], 0.0
    for i, s in enumerate(spec["segments"]):
        src, au = srcs[s["src"]], s.get("audio") or {}
        rngs = plan[i]
        vlen = sum(b - a for a, b in rngs)
        alen = sum(b_ - a_ for a_, b_ in au["chunks"]) if au.get("chunks") else (au["end"] - au["start"] if au else 0.0)
        dur = frames(vlen if (au.get("warp") or not au) else max(vlen, alen + s.get("tail", 0.0)))
        if s.get("vfit") and au and not au.get("warp"):  # 声は自然な速さのまま、映像の速さを声の長さに合わせる（速くも遅くもする）
            dur = frames(alen / float(s.get("atempo", 1.0)) + s.get("tail", 0.0))
        key = json.dumps(["onset-v1", s, rngs, anchors_of.get(i), [heads.get((i, k)) for k in range(len(rngs))], spec.get("brightness")],
                         sort_keys=True, ensure_ascii=False)
        out = work / f"seg_{i:02d}.mp4"
        meta = out.with_suffix(".key")
        if not out.exists() or not meta.exists() or meta.read_text() != key:
            # 映像：範囲ごとに SDR 化 → 頭の位置合わせ → つなぐ
            pieces, cams = [], []
            for k, (a, b) in enumerate(rngs):
                clip = sdr(p, src, a, b - a)
                vf = f"fps={FPS},scale={W}:{H}"
                if s.get("greenfix"):  # グリーンバックの上に映り込んだ天井を、すぐ下の緑で塗りつぶす（y は 1080×1920 の座標）
                    gy = int(s["greenfix"])
                    vf += f",split[gm][gb];[gb]crop={W}:8:0:{gy}:exact=1,scale={W}:{gy}:flags=neighbor[gg];[gm][gg]overlay=0:0"
                if s.get("mosaic"):  # [x0,y0,x1,y1]（0〜1の割合）の範囲に軽くモザイク。block は粒の大きさ(px)
                    x0, y0, x1, y1 = s["mosaic"]
                    bw, bh = int(W * (x1 - x0)) // 2 * 2, int(H * (y1 - y0)) // 2 * 2
                    blk = s.get("block", 24)
                    vf += (f",split[mm][mb];[mb]crop={bw}:{bh}:{int(W * x0)}:{int(H * y0)},scale={bw // blk}:{bh // blk},"
                           f"scale={bw}:{bh}:flags=neighbor[mg];[mm][mg]overlay={int(W * x0)}:{int(H * y0)}")
                if (i, k) in heads:
                    ty, tx = heads[(i, k)]
                    zw, zh = int(W * LOCK_ZOOM) // 2 * 2, int(H * LOCK_ZOOM) // 2 * 2
                    ox = int(max(0, min(zw - W, tx * zw - HEAD_X * W - float(s.get("xfix", 0.0)) * W)))  # xfix: 人物を右へ動かす割合（画面幅に対して。負なら左）
                    oy = int(max(0, min(zh - H, ty * zh - HEAD_TOP * H)))
                    vf += f",scale={zw}:{zh},crop={W}:{H}:{ox}:{oy}"
                elif s.get("xfix"):  # 頭の位置合わせをしない映像でも、人物を横にずらして中央に寄せる（少し拡大して端を隠す）
                    xz = float(s.get("xzoom", 1.14))
                    zw, zh = int(W * xz) // 2 * 2, int(H * xz) // 2 * 2
                    ox = int(max(0, min(zw - W, (zw - W) / 2 - float(s["xfix"]) * W)))
                    vf += f",scale={zw}:{zh},crop={W}:{H}:{ox}:{(zh - H) // 2}"
                if (s.get("style") == "split" or s.get("layout") == "split") and not s.get("stacked"):  # 上半分に人物（顔中心）、下半分は黒
                    vf += f",crop={W}:{H // 2}:0:{int(H * 0.08)},pad={W}:{H}:0:0:black"
                zz = (s.get("zooms") or [1.0] * len(rngs))[k]
                if zz and abs(zz - 1.0) > 0.001:  # 同じ動作の繰り返しに見えないよう、カットごとに寄りを変える（頭の位置は保つ）
                    zw, zh = int(W * zz) // 2 * 2, int(H * zz) // 2 * 2
                    vf += f",scale={zw}:{zh},crop={W}:{H}:{(zw - W) // 2}:{int((zh - H) * s.get('zoom_y', 0.12))}"
                spd = (s.get("vspeeds") or [1.0] * len(rngs))[k]  # 区間ごとの映像の速さ（声を伸ばさず、口の動きの方を速める）
                if spd != 1.0:
                    vf += f",setpts=PTS/{spd}"
                vf += f",eq=brightness={spec.get('brightness', 0.03)}:saturation=1.04"
                if s.get("vfx"):  # 区間ごとの追加の映像効果（ffmpeg のフィルター文字列）。例：白黒＋赤み、白フラッシュ
                    vf += "," + s["vfx"]
                vf += ",format=yuv420p"
                pv = work / f"seg_{i:02d}_{k}.mp4"
                ad.run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-vf", vf, "-t", f"{(b - a) / spd:.4f}", "-an",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-g", str(FPS), pv])
                if s.get("bg"):  # グリーンバックを背景写真に差し替え、人物の色味をととのえる
                    kv = work / f"seg_{i:02d}_{k}_key.mp4"
                    ad.run([ad.STUDIO / "tools/.keyenv/bin/python", ad.STUDIO / "tools/keybg.py", pv, p.dir / s["bg"], kv,
                            *sum([[f"--{n}", str(v)] for n, v in (s.get("grade") or {}).items()], [])])
                    pv = kv
                pieces.append(pv)
                cw = work / f"seg_{i:02d}_{k}_cam.wav"
                if not au.get("warp"):
                    continue
                ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", src,
                        "-map", "0:a:0", "-ac", "1", "-ar", "16000", cw])
                cams.append(cw)
            lst = work / f"seg_{i:02d}_list.txt"
            lst.write_text("".join(f"file '{x.name}'\n" for x in pieces))
            vid = work / f"seg_{i:02d}_v.mp4"
            ad.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid])
            # 音声
            wav = work / f"seg_{i:02d}.wav"
            if au.get("warp"):
                cam = work / f"seg_{i:02d}_cam.wav"
                ad.run(["ffmpeg", "-y", "-v", "error", *sum([["-i", c] for c in cams], []), "-filter_complex",
                        "".join(f"[{k}:a]" for k in range(len(cams))) + f"concat=n={len(cams)}:v=0:a=1[a]",
                        "-map", "[a]", cam])
                stretch(p, cleans[i], anchors_of[i], dur, wav)
                if len(rngs) == 1 and s.get("onset", True):
                    sh = align_onset(src, rngs[0][0], rngs[0][1], wav, dur)
                    if sh:
                        ad.log(f"区間{i}: 話し始めを {sh * 1000:+.0f}ms そろえました")
            elif s.get("phrases"):  # 区切りごとに、別録り音声を本人の撮影時の音と音の形（DTW）で比べて、口の動きに合わせて伸縮する
                parts_a = []
                for k, ph in enumerate(s["phrases"]):
                    (va, vb) = ph["voice"]
                    rs = ph.get("vs") or [ph["v"]]  # 声を一続きにして、複数の映像範囲（カット）をまたいで流すときは vs
                    sp = (s.get("vspeeds") or [1.0] * len(s["phrases"]))[k]
                    ra, rb = 0.0, sum(b_ - a_ for a_, b_ in rs) / sp
                    wa, cw = work / f"seg_{i:02d}_p{k}_a.wav", work / f"seg_{i:02d}_p{k}_cam.wav"
                    ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{va:.3f}", "-to", f"{vb:.3f}", "-i", p.dir / s["audio_file"],
                            "-ac", "1", "-ar", "16000", wa])
                    ins_c = sum([["-ss", f"{a_:.3f}", "-to", f"{b_:.3f}", "-i", src] for a_, b_ in rs], [])
                    fc_c = "".join(f"[{m}:a:0]aresample=16000,aformat=channel_layouts=mono[c{m}];" for m in range(len(rs))) + \
                        "".join(f"[c{m}]" for m in range(len(rs))) + f"concat=n={len(rs)}:v=0:a=1[a]"
                    ad.run(["ffmpeg", "-y", "-v", "error", *ins_c, "-filter_complex", fc_c, "-map", "[a]", "-ar", "16000", "-ac", "1", cw])
                    pts, ms, me = dtw_map(wa, cw)
                    (x0, x1), (y0, y1) = speech_span(wa), speech_span(cw)  # 声の出始め・終わりを、本人の口の出始め・終わりに強制的にそろえる
                    ms, me = max(0.0, y0 - x0), y1 + ((vb - va) - x1)
                    if ph.get("lin") and x1 > x0:  # lin: 声の出始め〜終わりを口の出始め〜終わりへ等速で対応させる割合（0〜1）を DTW と混ぜる
                        pts = [(x, (1 - ph["lin"]) * y + ph["lin"] * (y0 + (x - x0) / (x1 - x0) * (y1 - y0))) for x, y in pts]
                    anc, last = [(0.0, ms)], (0.0, ms)
                    for x, y in pts:
                        if x0 + 0.12 <= x <= x1 - 0.12 and x - last[0] >= 0.15 and y - last[1] >= 0.08 \
                                and 0.5 <= (x - last[0]) / (y - last[1]) <= 2.0 and y1 - 0.1 >= y >= y0 + 0.1:
                            anc.append((x, y))
                            last = (x, y)
                    anc.append((vb - va, max(last[1] + 0.05, me)))
                    if sp != 1.0:
                        anc = [(x, y / sp) for x, y in anc]
                    outk = work / f"seg_{i:02d}_p{k}.wav"
                    stretch(p, {"file": s["audio_file"], "start": va, "end": vb}, anc, rb - ra, outk)
                    parts_a.append(outk)
                ad.run(["ffmpeg", "-y", "-v", "error", *sum([["-i", x] for x in parts_a], []), "-filter_complex",
                        "".join(f"[{k}:a]" for k in range(len(parts_a))) + f"concat=n={len(parts_a)}:v=0:a=1[a]",
                        "-map", "[a]", "-ar", "48000", "-ac", "2", wav])
            elif not au and s.get("native_audio"):  # 映像の撮影時の音をそのまま使う（口と音は元から合っている）
                ins, fc = [], ""
                for k, (a0, b0) in enumerate(rngs):  # 範囲ごとに音を切り出し、つなぎ目に極短いフェードを入れてつなぐ
                    ins += ["-ss", f"{a0:.3f}", "-to", f"{b0:.3f}", "-i", src]
                    fc += f"[{k}:a:0]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.012,afade=t=out:st={b0 - a0 - 0.012:.3f}:d=0.012[n{k}];"
                fc += "".join(f"[n{k}]" for k in range(len(rngs))) + (
                    f"concat=n={len(rngs)}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{dur:.4f}[a]")
                ad.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc, "-map", "[a]", "-ar", "48000", "-ac", "2", wav])
            elif not au:
                ad.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{dur:.4f}", "-i",
                        "anullsrc=r=48000:cl=stereo", wav])
            elif au.get("chunks"):  # 間（無音）を抜いて、音声の複数の範囲をつなぐ
                ins_a = sum([["-ss", f"{a_:.3f}", "-to", f"{b_:.3f}", "-i", p.dir / au["file"]] for a_, b_ in au["chunks"]], [])
                fc_a = "".join(f"[{m}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.008,afade=t=out:st={max(0.0, b_ - a_ - 0.008):.3f}:d=0.008[n{m}];"
                               for m, (a_, b_) in enumerate(au["chunks"]))
                fc_a += "".join(f"[n{m}]" for m in range(len(au["chunks"]))) + f"concat=n={len(au['chunks'])}:v=0:a=1,apad,atrim=0:{dur:.4f}[a]"
                ad.run(["ffmpeg", "-y", "-v", "error", *ins_a, "-filter_complex", fc_a, "-map", "[a]", "-ar", "48000", "-ac", "2", wav])
            else:
                ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{au['start']:.3f}", "-to", f"{au['end']:.3f}",
                        "-i", p.dir / au["file"], "-af",
                        f"adelay={int(s.get('lead', 0.0) * 1000)}:all=1,"
                        + (f"atempo={float(s['atempo']):.4f}," if s.get("atempo") else "")  # 声の速さを少し変える（1.0未満＝ゆっくり）
                        + (s["afx"] + "," if s.get("afx") else "")  # 区間ごとの追加の音声フィルター（EQ・音量など）
                        + f"afade=t=in:d=0.02,apad,atrim=0:{dur:.4f}",
                        "-ar", "48000", "-ac", "2", wav])
            slow = (dur / max(0.1, vlen)) if s.get("vfit") else max(1.0, dur / max(0.1, vlen))  # Bロールが音声より短いときはゆっくり再生（vfit は速くもする）
            ad.run(["ffmpeg", "-y", "-v", "error", "-i", vid, "-i", wav, "-map", "0:v", "-map", "1:a", "-vf",
                    f"setpts={slow:.4f}*PTS,fps={FPS},tpad=stop_mode=clone:stop_duration=2", "-t", f"{dur:.4f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-g", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out])
            meta.write_text(key)
        segs.append({**s, "i": i, "at": round(t, 4), "len": dur, "file": out, "who": "nakamura",
                     "v": [round(t, 4), round(t + dur, 4)], "ranges": rngs})
        t += dur
    return segs


BADGE_CSS = """
.title { position: absolute; right: 40px; top: 150px; background: rgba(28,28,28,.78); color: #fff;
  font-size: 38px; font-weight: 700; padding: 10px 20px; letter-spacing: .02em; }
.cap.split { top: 1180px; }
.ctabox { font-size: 62px !important; left: 70px !important; right: 70px !important; padding: 26px 18px !important; }
.ovwrap { position: absolute; left: 0; right: 0; display: flex; justify-content: center; align-items: center; gap: 24px; }
.ovwrap.top { top: 200px; } .ovwrap.bottom { top: 1470px; }
.ovwrap.col { flex-direction: column; gap: 14px; }
.ovi { opacity: 0; }
.chip { display: inline-flex; align-items: center; gap: 14px; background: rgba(20,20,20,.9); color: #fff; font-weight: 900;
  font-size: 80px; padding: 18px 48px; border-radius: 90px; border: 6px solid #FFE600; white-space: nowrap;
  box-shadow: 0 8px 20px rgba(0,0,0,.35); letter-spacing: .02em; }
.chip.y { background: #FFE600; color: #111; border-color: #fff; font-size: 112px; padding: 12px 60px; }
.chip.mini { background: rgba(60,60,60,.88); color: #ddd; border-color: #aaa; font-size: 62px; }
.chip.g { border-color: #2BEA62; }
.chip .no { color: #FFE600; font-size: 66px; }
.chip svg { display: block; width: 1.0em; height: auto; max-height: 1.0em; }
.namecard { display: inline-flex; align-items: center; gap: 24px; background: #fff; color: #111; padding: 18px 44px 18px 22px;
  border-radius: 28px; border-left: 14px solid #F28C28; box-shadow: 0 10px 26px rgba(0,0,0,.4); }
.namecard img { width: 156px; height: 156px; border-radius: 50%; display: block; }
.namecard .t1 { font-size: 88px; font-weight: 900; line-height: 1.1; }
.namecard .t2 { font-size: 50px; font-weight: 800; color: #555; }
.impact-host .cap { top: 130px !important; }
.impact-host .blk { font-size: 150px !important; font-weight: 900 !important; line-height: 1.04 !important; text-align: center; color: #fff;
  letter-spacing: -.01em; transform: none !important;
  -webkit-text-stroke: 16px #111; paint-order: stroke fill;
  text-shadow: -10px 0 #111, 10px 0 #111, 0 -10px #111, 0 10px #111, -8px -8px #111, 8px -8px #111, -8px 8px #111, 8px 8px #111,
               0 16px 0 rgba(0,0,0,.5), 0 0 34px rgba(0,0,0,.6) !important; }
.impact-host .blk .ln { text-align: center; align-self: center !important; }
.impact-host .y { color: #FFE600 !important; }
.impact-host .r { color: #FF2A1F !important; }
.impact-host .big { color: #FF2A1F !important; font-size: 1em !important; transform: none !important; display: inline; line-height: 1.0; }
.ft { position: absolute; font-family: "Hiragino Mincho ProN", "Noto Serif JP", serif; white-space: nowrap; line-height: 1.04; }
.ft.vw, .ft.vr { writing-mode: vertical-rl; text-combine-upright: digits 2; font-weight: 800; transform-origin: 50% 0; }
.ft.vw { color: #fff; -webkit-text-stroke: 14px #111; paint-order: stroke fill;
  text-shadow: 0 8px 14px rgba(0,0,0,.55), 0 0 22px rgba(0,0,0,.35); }
.ft.vr { color: #FF2A1F; -webkit-text-stroke: 9px #fff; paint-order: stroke fill; font-weight: 900;
  filter: drop-shadow(0 0 0 #1B3FD8) drop-shadow(0 7px 10px rgba(0,0,0,.5)); }
.ft.vr::before { content: attr(data-t); position: absolute; inset: 0; z-index: -1; color: #1B3FD8; -webkit-text-stroke: 30px #1B3FD8;
  writing-mode: vertical-rl; text-combine-upright: digits 2; }
.ft.hb { font-family: "Noto", sans-serif; font-weight: 900; color: #2A5CFF; transform: skewX(-9deg);
  -webkit-text-stroke: 15px #fff; paint-order: stroke fill; text-shadow: 0 8px 14px rgba(0,0,0,.45); }
.qbox { position: absolute; left: 50%; margin-left: -330px; width: 660px; border-radius: 30px; overflow: hidden;
  box-shadow: 0 14px 34px rgba(0,0,0,.38); font-family: "Noto", sans-serif; text-align: center; }
.qbox .qh { background: #1c1c1e; color: #fff; font-size: 34px; font-weight: 800; padding: 20px 0 18px; letter-spacing: .04em; }
.qbox .qb .rd { color: #FF2A1F; }
.qbox .qb { background: #fff; color: #111; font-size: 50px; font-weight: 800; line-height: 1.3; padding: 26px 18px 30px; }
.ft.vi { writing-mode: vertical-rl; text-combine-upright: digits 2; font-family: "Noto", sans-serif; font-weight: 900; color: #fff;
  -webkit-text-stroke: 18px #111; paint-order: stroke fill; line-height: 1.0; transform-origin: 50% 0;
  text-shadow: 0 10px 0 rgba(0,0,0,.45), 0 0 30px rgba(0,0,0,.5); }
.ft.vi .tcy { text-combine-upright: all; -webkit-text-combine: horizontal; }
.ft.vi .rd { color: #FF2A1F; } .ft.vi .yw { color: #FFE600; }
.ft.vt { writing-mode: vertical-rl; text-combine-upright: digits 2; font-family: "Noto", sans-serif; font-weight: 900; color: #fff;
  line-height: 1.06; transform-origin: 50% 0;
  text-shadow: 0 0 2px rgba(0,0,0,1), 0 0 6px rgba(0,0,0,.9), 0 0 14px rgba(0,0,0,.6), 0 6px 14px rgba(0,0,0,.6); }
.ft.vt.cy { color: #FFE600; }
.ft.vt .yw { color: #FFE600; } .ft.vt .rd { color: #FF2A1F; } .ft.vt .tcy { text-combine-upright: all; }
.ft.hw { color: #fff; font-weight: 800; -webkit-text-stroke: 12px #111; paint-order: stroke fill; text-shadow: 0 7px 12px rgba(0,0,0,.5); }
.logo { position: absolute; left: 50%; transform: translateX(-50%); }
.logo.icon img { border-radius: 50%; box-shadow: 0 6px 16px rgba(0,0,0,.35); border: 5px solid #fff; box-sizing: content-box; }
.logo.plate { background: #fff; border-radius: 16px; padding: 16px 30px; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
.circle { position: absolute; left: 90px; top: 1225px; width: 900px; height: 210px; }
.circle ellipse { fill: none; stroke: #FFE600; stroke-width: 9; stroke-linecap: round; }
"""


def apply_inserts(p: ad.Project, spec: dict, segs: list[dict], base: Path, work: Path) -> Path:
    """人物の映像の途中に、別の映像をはさむ（声とテロップはそのまま）。inserts: [{from:{seg,part,f}, to:{seg,part,f}, src, v:[開始,終了]}]"""
    srcs = {k: p.dir / v for k, v in spec["sources"].items()}

    def at(ref):
        sg = next(x for x in segs if x["telop"].startswith(ref["seg"]))
        pt = sg["parts"][ref["part"]]
        return pt["start"] + ref["f"] * (pt["end"] - pt["start"])
    ins, fc, last = [], "", "[0:v]"
    for n, it in enumerate(spec["inserts"]):
        ts, te = at(it["from"]), at(it["to"])
        a, b = it["v"]
        dur = te - ts
        clip = sdr(p, srcs[it["src"]], a, max(dur, b - a))
        ins += ["-i", clip]
        fc += (f"[{n + 1}:v]fps={FPS},scale={W}:{H},trim=duration={dur:.3f},setpts=PTS-STARTPTS+{ts:.3f}/TB,format=yuva420p,"
               f"fade=t=in:st={ts:.3f}:d=0.08:alpha=1,fade=t=out:st={te - 0.08:.3f}:d=0.08:alpha=1[b{n}];"
               f"{last}[b{n}]overlay=eof_action=pass:format=auto:enable='between(t,{ts:.3f},{te:.3f})'[v{n}];")
        last = f"[v{n}]"
    out = work / "base_ins.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", base, *ins, "-filter_complex", fc.rstrip(";"), "-map", last, "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-g", str(FPS), "-pix_fmt", "yuv420p", out])
    return out


def qrich(line: str) -> str:
    """質問箱の本文：#語# を赤字に。"""
    parts = line.split("#")
    return "".join(f'<span class="rd">{escape(x)}</span>' if k % 2 else escape(x) for k, x in enumerate(parts))


def vrich(line: str) -> str:
    """縦書きインパクト：#語# 赤、*語* 黄。"""
    out = escape(line)
    out = re.sub(r"#(.+?)#", r'<span class="rd">\1</span>', out)
    out = re.sub(r"\*(.+?)\*", r'<span class="yw">\1</span>', out)
    def tx(html_: str, pat: str) -> str:  # タグの外の文字だけ変換する（縦書きで数字・英字を横倒しにしない）
        return "".join(x if x.startswith("<") else re.sub(pat, r'<span class="tcy">\1</span>', x)
                       for x in re.split(r"(<[^>]+>)", html_))
    out = tx(out, r"(\d{1,2})")
    return tx(out, r"([A-Za-z]{1,3})")


def compose(p: ad.Project, segs: list[dict], total: float, base: Path, audio: Path,
            hf: Path | None = None, media_start: float = 0.0) -> None:
    """見た目は CR25 型（talk.compose）。肩書き・split・CTA の丸を書く演出を足す。"""
    ORIG(p, segs, total, base, audio, hf=hf, media_start=media_start)
    hf = hf or p.hf
    html = (hf / "index.html").read_text(encoding="utf-8")
    extra, js = [], []
    title = SPEC.get("title_badge")
    if title:
        extra.append(f'<div id="ttl" class="clip layer" data-start="0" data-duration="{total:.3f}" data-track-index="6">'
                     f'<div class="title">{escape(title)}</div></div>')
    for s in segs:
        if s.get("style") == "cta" and s.get("circle"):
            ls, le = s["at"], round(s["at"] + s["len"], 3)
            extra.append(f'<div id="o{s["i"]}" class="clip layer" data-start="{ls:.3f}" data-duration="{le - ls:.3f}" '
                         f'data-track-index="7"><svg class="circle" viewBox="0 0 900 210"><ellipse cx="450" cy="105" '
                         f'rx="436" ry="92" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg></div>')
            js.append(f'tl.fromTo("#o{s["i"]} ellipse",{{strokeDashoffset:1}},{{strokeDashoffset:0,duration:0.6,'
                      f'ease:"power1.inOut"}},{ls + 0.5:.3f});')
    for s in segs:  # ロゴ画像（テロップの下など）。logo: {"file", "y", "w"}
        lg = s.get("logo")
        if lg and not (p.dir / lg["file"]).exists():
            ad.log(f"ロゴ画像が見つかりません（{lg['file']}）。ロゴなしで書き出します")
        elif lg:
            src_logo = p.dir / lg["file"]
            (hf / src_logo.name).write_bytes(src_logo.read_bytes())
            extra.append(f'<div id="lg{s["i"]}" class="clip layer" data-start="{s["at"]:.3f}" data-duration="{s["len"]:.3f}" '
                         f'data-track-index="8"><div class="logo{" plate" if lg.get("plate", True) else ("" if lg.get("raw") else " icon")}" style="top:{lg.get("y", 1500)}px"><img src="{src_logo.name}" '
                         f'style="width:{lg.get("w", 150)}px;display:block"></div></div>')
    for s in segs:
        if s.get("style") == "cta" and s.get("pulse"):  # 「画面下のリンクから」の枠を、大きくして脈動（拡大縮小）させる
            ls, le = s["at"], s["at"] + s["len"]
            k = max(1, int((le - ls - 0.3) / 0.44))
            js.append(f'tl.to("#c{s["i"]} .ctabox",{{scale:1.1,duration:0.22,yoyo:true,repeat:{2 * k - 1},ease:"sine.inOut",'
                      f'transformOrigin:"50% 50%"}},{ls + 0.3:.3f});')
    for s in segs:  # 図解の重ね（カード・チェック・名前カード）。overlays: [{part, from, to, pos, items:[{html, at}], assets}]
        for n, o in enumerate([] if SPEC.get("disable_overlays") else (s.get("overlays") or [])):
            part = s["parts"][o["part"]]
            d = part["end"] - part["start"]
            ts, te = part["start"] + o.get("from", 0.0) * d, part["start"] + o.get("to", 1.0) * d
            for f in o.get("assets") or []:
                src_f = p.dir / f
                (hf / src_f.name).write_bytes(src_f.read_bytes())
            eid = f"ov{s['i']}_{n}"
            inner = "".join(f'<div id="{eid}_{m}" class="ovi">{it["html"]}</div>' for m, it in enumerate(o["items"]))
            extra.append(f'<div id="{eid}" class="clip layer" data-start="{ts:.3f}" data-duration="{te - ts:.3f}" '
                         f'data-track-index="9"><div class="ovwrap {o.get("pos", "top")}{" col" if o.get("stack") else ""}">{inner}</div></div>')
            for m, it in enumerate(o["items"]):
                t0 = ts + it.get("at", 0.0) * (te - ts)
                js.append(f'tl.fromTo("#{eid}_{m}",{{scale:0.6,opacity:0,y:-18}},{{scale:1,opacity:1,y:0,duration:0.24,'
                          f'ease:"back.out(2.2)"}},{t0:.3f});')
    for s in segs:  # 参考動画風の自由テロップ。ftele: [{t, kind(vw 白縦書き明朝/vr 赤縦書き/hb 青斜体/hw 白横書き明朝), at, to, side(r/l), top, size, x}]（at/to は区間の頭からの秒）
        for m, it in enumerate(s.get("ftele") or []):
            t0, t1 = s["at"] + it.get("at", 0.0), s["at"] + min(it.get("to", s["len"]), s["len"])
            eid = f"ft{s['i']}_{m}"
            if it.get("kind") == "qbox":  # Instagram の質問箱風：右から飛んできて止まり、手のひと振りで右へ飛んでいく
                t1 += 0.35
                extra.append(f'<div id="{eid}" class="clip layer" data-start="{t0:.3f}" data-duration="{t1 - t0:.3f}" data-track-index="11">'
                             f'<div class="qbox" style="top:{it.get("top", 1000)}px;{("width:%dpx;margin-left:-%dpx;" % (it["w"], it["w"] // 2)) if it.get("w") else ""}"><div class="qh">{escape(it.get("h", "質問来てた"))}</div>'
                             f'<div class="qb">{"<br>".join(qrich(x) for x in it["t"].split("/"))}</div></div></div>')
                js.append(f'tl.fromTo("#{eid} .qbox",{{x:900,rotation:14,opacity:0}},{{x:0,rotation:0,opacity:1,duration:0.32,ease:"back.out(1.5)"}},{t0:.3f});')
                if it.get("to") is not None:
                    te = s["at"] + it["to"]
                    lft = it.get("exit") == "left"
                    js.append(f'tl.to("#{eid} .qbox",{{x:{-1250 if lft else 1250},rotation:{-20 if lft else 20},opacity:0.0,duration:0.3,ease:"power2.in"}},{te:.3f});')
                continue
            pos = f'top:{it.get("top", 300)}px;font-size:{it.get("size", 140)}px;'
            kind = it.get("kind", "vw")
            if kind in ("hb", "hw"):
                pos += f'left:0;right:0;text-align:center;' if "x" not in it else f'left:{it["x"]}px;'
            else:
                pos += (f'right:{it.get("x", 40)}px;' if it.get("side", "r") == "r" else f'left:{it.get("x", 40)}px;')
            extra.append(f'<div id="{eid}" class="clip layer" data-start="{t0:.3f}" data-duration="{t1 - t0:.3f}" data-track-index="10">'
                         f'<div class="ft {kind}{" cy" if it.get("c") == "y" else ""}" data-t="{escape(it["t"])}" style="{pos}">{vrich(it["t"]) if kind in ("vi", "vt") else escape(it["t"])}</div></div>')
            fx = (-34 if it.get("side", "r") == "r" else 34) if kind in ("vw", "vr", "vi", "vt") else 0
            js.append(f'tl.fromTo("#{eid} .ft",{{opacity:0,x:{fx},y:{0 if fx else 24},scale:{1 if fx else 0.9}}},{{opacity:1,x:0,y:0,scale:1,'
                      f'duration:0.2,ease:"power2.out"}},{t0:.3f});')
    html = html.replace("</style>", BADGE_CSS + "</style>", 1)
    # edit.json の css / font_file / tone_css / 区間の tones: 参考動画風テロップ（フォント・縁取り・色替え）を案件ごとに指定する
    css_extra = SPEC.get("css", "")
    if SPEC.get("font_file"):
        (hf / "fonts").mkdir(exist_ok=True)
        (hf / "fonts/tele.ttf").write_bytes((ad.STUDIO / SPEC["font_file"]).read_bytes())
        css_extra = '@font-face { font-family: "Tele"; src: url("fonts/tele.ttf") format("truetype"); }\n' + css_extra
    for s_ in segs:
        for k_, tn in enumerate(s_.get("tones") or []):
            if tn:
                css_extra += f'#s{s_["i"]}_{k_} .blk {{ {SPEC["tone_css"][tn]} }}\n'
    if css_extra:
        html = html.replace("</style>", css_extra + "</style>", 1)
    html = html.replace('class="cap"', 'class="cap"')
    for s in segs:  # split の区間はテロップを下半分（黒地）に
        if s.get("style") == "split":
            for k in range(len(s["parts"])):
                html = html.replace(f'id="s{s["i"]}_{k}" class="clip layer" data-start',
                                    f'id="s{s["i"]}_{k}" class="clip layer split-host" data-start', 1)
    html = re.sub(r'(class="clip layer split-host"[^>]*><div class=")cap', r"\1cap split", html)
    sizes_css = ""
    for s in segs:  # 冒頭の「インパクト」テロップ（太い縁取り・大きい赤/黄）。impact_sizes: 画面ごとの1行目・2行目…の文字の大きさ(px)
        for k, row in enumerate(s.get("impact_sizes") or []):
            for m, px in enumerate(row):
                sizes_css += f'#s{s["i"]}_{k} .blk .ln:nth-child({m + 1}) {{ font-size: {px}px !important; }}\n'
    for s in segs:  # cap_top: この区間のテロップの上端(px)。人物に被るとき、頭の上などへ上げる
        if s.get("cap_top") is not None:
            for k in range(len(s["parts"])):
                sizes_css += f'#s{s["i"]}_{k} .cap {{ top: {int(s["cap_top"])}px !important; }}\n'
    for s in segs:  # impact_top: テロップの上端(px)。人物の顔にかからない位置に下げたいとき
        if s.get("impact_top") is not None:
            for k in range(len(s["parts"])):
                sizes_css += f'#s{s["i"]}_{k} .cap {{ top: {int(s["impact_top"])}px !important; }}\n'
    for s in segs:  # ftele を使う区間は、元のテロップを画面に出さない（時刻と効果音の目安としては残す）
        if any(it.get("kind") != "qbox" or it.get("hide_telop") for it in (s.get("ftele") or [])):
            for k in range(len(s["parts"])):
                sizes_css += f'#s{s["i"]}_{k} {{ display: none !important; }}\n'
    if sizes_css:
        html = html.replace("</style>", sizes_css + "</style>", 1)
    for s in segs:  # 冒頭の「インパクト」テロップ（太い縁取り・大きい赤/黄）
        if s.get("style") == "impact":
            for k in range(len(s["parts"])):
                html = html.replace(f'id="s{s["i"]}_{k}" class="clip layer" data-start',
                                    f'id="s{s["i"]}_{k}" class="clip layer impact-host" data-start', 1)
    html = html.replace("\n</div>\n<script>", "\n" + "\n".join(extra) + "\n</div>\n<script>", 1)
    html = html.replace("window.__timelines", "\n".join(js) + "\nwindow.__timelines", 1)
    (hf / "index.html").write_text(html, encoding="utf-8")


SPEC: dict = {}
ORIG = talk.compose


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--variant", default="")
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    p = ad.Project(a.name)
    spec = ad.load_json(p.dir / "edit.json")
    tag = ""
    if a.variant:
        v = spec["variants"][a.variant]
        drop = set(v.get("drop", []))
        spec = {**spec, "segments": [s for i, s in enumerate(spec["segments"]) if i not in drop]}
        tag = f"_{a.variant}"
    SPEC.update(spec)
    work = p.edit / f"ugc{tag}"
    work.mkdir(parents=True, exist_ok=True)
    segs = build(p, spec, work)
    total = round(sum(s["len"] for s in segs), 4)
    ad.log(f"{len(segs)} 区間・{total:.1f} 秒")
    (work / "list.txt").write_text("".join(f"file '{s['file'].name}'\n" for s in segs))
    joined = work / "joined.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", work / "list.txt", "-c", "copy", joined])
    base = work / "base.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", joined, "-vf",
            f"fps={FPS},scale={W}:{H}:flags=lanczos:in_range=full:out_range=tv,format=yuv420p,"
            "tpad=stop_mode=clone:stop_duration=1", "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-g", str(FPS), "-keyint_min", str(FPS), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", base])
    audio = work / "voice.m4a"
    # 区間ごとの音声（wav）を、映像と同じ長さに合わせてつなぐ。AAC の区間をつなぐと1区間ごとに数十ミリ秒ずれが積もるため
    ins, fc = [], ""
    for k, sg in enumerate(segs):
        ins += ["-i", work / f"seg_{sg['i']:02d}.wav"]
        fc += f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={sg['len']:.4f},atrim=0:{sg['len']:.4f},asetpts=PTS-STARTPTS[a{k}];"
    fc += "".join(f"[a{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1[a]"
    ad.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc, "-map", "[a]", "-c:a", "aac", "-b:a", "192k", audio])
    words = ad.transcribe_whisper(audio, work / "voice_words.json")
    talk.caption_parts(segs, words)
    ad.save_json(work / "timeline.json", [{k: (str(v) if isinstance(v, Path) else v) for k, v in s.items()} for s in segs])
    if spec.get("inserts"):
        base = apply_inserts(p, spec, segs, base, work)
    talk.compose = compose
    compose(p, segs, total, base, audio)
    raw = talk.render_parts(p, segs, total, base, audio, work, a.draft)
    final = ad.loudnorm_to_output(p, raw, suffix=tag + ("_draft" if a.draft else ""))
    ad.log(f"→ {final.relative_to(ad.STUDIO)}")


if __name__ == "__main__":
    main()
