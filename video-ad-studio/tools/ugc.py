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
        tempo = max(0.55, min(1.8, (x1 - x0) / max(0.02, y1 - y0)))
        fc += (f"[0:a]atrim={a + x0:.4f}:{a + x1:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
               f"aformat=channel_layouts=mono,atempo={tempo:.4f}[p{k}];")
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
        if au.get("warp"):
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
        dur = frames(vlen if (au.get("warp") or not au) else max(vlen, au["end"] - au["start"] + s.get("tail", 0.0)))
        key = json.dumps([s, rngs, anchors_of.get(i), [heads.get((i, k)) for k in range(len(rngs))], spec.get("brightness")],
                         sort_keys=True, ensure_ascii=False)
        out = work / f"seg_{i:02d}.mp4"
        meta = out.with_suffix(".key")
        if not out.exists() or not meta.exists() or meta.read_text() != key:
            # 映像：範囲ごとに SDR 化 → 頭の位置合わせ → つなぐ
            pieces, cams = [], []
            for k, (a, b) in enumerate(rngs):
                clip = sdr(p, src, a, b - a)
                vf = f"fps={FPS},scale={W}:{H}"
                if (i, k) in heads:
                    ty, tx = heads[(i, k)]
                    zw, zh = int(W * LOCK_ZOOM) // 2 * 2, int(H * LOCK_ZOOM) // 2 * 2
                    ox = int(max(0, min(zw - W, tx * zw - HEAD_X * W)))
                    oy = int(max(0, min(zh - H, ty * zh - HEAD_TOP * H)))
                    vf += f",scale={zw}:{zh},crop={W}:{H}:{ox}:{oy}"
                if s.get("style") == "split":  # 上半分に人物（顔中心）、下半分は黒
                    vf += f",crop={W}:{H // 2}:0:{int(H * 0.08)},pad={W}:{H}:0:0:black"
                vf += f",eq=brightness={spec.get('brightness', 0.03)}:saturation=1.04,format=yuv420p"
                pv = work / f"seg_{i:02d}_{k}.mp4"
                ad.run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-vf", vf, "-t", f"{b - a:.4f}", "-an",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-g", str(FPS), pv])
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
            elif not au:
                ad.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{dur:.4f}", "-i",
                        "anullsrc=r=48000:cl=stereo", wav])
            else:
                ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{au['start']:.3f}", "-to", f"{au['end']:.3f}",
                        "-i", p.dir / au["file"], "-af",
                        f"adelay={int(s.get('lead', 0.0) * 1000)}:all=1,afade=t=in:d=0.02,apad,atrim=0:{dur:.4f}",
                        "-ar", "48000", "-ac", "2", wav])
            slow = max(1.0, dur / max(0.1, vlen))  # Bロールが音声より短いときはゆっくり再生
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
.circle { position: absolute; left: 90px; top: 1225px; width: 900px; height: 210px; }
.circle ellipse { fill: none; stroke: #FFE600; stroke-width: 9; stroke-linecap: round; }
"""


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
    html = html.replace("</style>", BADGE_CSS + "</style>", 1)
    html = html.replace('class="cap"', 'class="cap"')
    for s in segs:  # split の区間はテロップを下半分（黒地）に
        if s.get("style") == "split":
            for k in range(len(s["parts"])):
                html = html.replace(f'id="s{s["i"]}_{k}" class="clip layer" data-start',
                                    f'id="s{s["i"]}_{k}" class="clip layer split-host" data-start', 1)
    html = re.sub(r'(class="clip layer split-host"[^>]*><div class=")cap', r"\1cap split", html)
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
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", joined, "-vn", "-c:a", "aac", "-b:a", "192k", audio])
    words = ad.transcribe_whisper(audio, work / "voice_words.json")
    talk.caption_parts(segs, words)
    ad.save_json(work / "timeline.json", [{k: (str(v) if isinstance(v, Path) else v) for k, v in s.items()} for s in segs])
    talk.compose = compose
    compose(p, segs, total, base, audio)
    raw = talk.render_parts(p, segs, total, base, audio, work, a.draft)
    final = ad.loudnorm_to_output(p, raw, suffix=tag + ("_draft" if a.draft else ""))
    ad.log(f"→ {final.relative_to(ad.STUDIO)}")


if __name__ == "__main__":
    main()
