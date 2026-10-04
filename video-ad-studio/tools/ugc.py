#!/usr/bin/env python3
"""つぎはぎ UGC 型（参考：CR12）を edit.json から組み立てる。映像と別録り音声を口に合わせて当てる。

  python3 tools/ugc.py <name> [--variant 冒頭1] [--draft]

edit.json の segments（上から順につなぐ）:
- src: sources のキー（映像）。null なら黒画面（style: black）
- v: [開始, 終了]（映像の秒）。終了が null なら音声の長さに合わせる（Bロール）
- audio: {"file", "start", "end"}  別録り音声の区間
    - "sync": 映像と同時録音。音声の長さ＝映像の長さ（start だけで決まる）
    - "warp": 別テイク。文字ごとに音声を少しだけ伸び縮みさせ、映像の口の動きに合わせる（±25%まで）
    - どちらでもなければ、そのまま乗せる（Bロール・黒画面）
- telop: '|' で次のテロップ、'/' で改行、*語* は少し大きく
- style: black（黒背景に白文字）
- punch: 寄るテロップ番号
テロップは CR12 準拠：明朝体の白文字＋やわらかい影、画面中央。右上に肩書き（title）。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ad  # noqa: E402
import talk  # noqa: E402

W, H, FPS = ad.W, ad.H, ad.FPS


def frames(t: float) -> float:
    return round(round(t * FPS) / FPS, 4)


def sdr(p: ad.Project, src: Path, a: float, dur: float) -> Path:
    """iPhone の HDR を avconvert で SDR・縦向き（1080×1920）に。区間ごとにキャッシュ。"""
    cache = p.edit / "sdr"
    cache.mkdir(exist_ok=True)
    out = cache / f"{src.stem}_{a:.2f}_{dur:.2f}.mp4"
    if not out.exists() or ad.ffprobe_duration(out) < dur - 0.1:
        preset = "Preset3840x2160" if "1009" in src.stem else "Preset1920x1080"
        ad.run(["avconvert", "-s", src, "-o", out, "-p", preset, "--start", f"{a:.3f}",
                "--duration", f"{dur + 0.3:.3f}", "--replace"], stdout=subprocess.DEVNULL)
    return out


def words_of(wav: Path) -> tuple[str, list[float]]:
    ws = ad.transcribe_whisper(wav, wav.with_suffix(".whisper.json"))
    return ad.char_times(ws) if ws else ("", [])


def warp_audio(p: ad.Project, work: Path, au: dict, vsrc: Path, va: float, vb: float, out: Path) -> None:
    """別テイクの音声を、映像側の同じ文字の時刻に合わせて区切りごとに伸縮する（口と音声を合わせる）。"""
    a, b = au["start"], au["end"]
    wa, wv = work / f"{out.stem}_a.wav", work / f"{out.stem}_v.wav"
    ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", p.dir / au["file"],
            "-ac", "1", "-ar", "16000", wa])
    ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{va:.3f}", "-to", f"{vb:.3f}", "-i", vsrc, "-map", "0:a:0",
            "-ac", "1", "-ar", "16000", wv])
    ta, tia = words_of(wa)
    tv, tiv = words_of(wv)
    na, nv = [ad.norm(c) for c in ta], [ad.norm(c) for c in tv]
    anchors = [(0.0, 0.0)]
    for blk in difflib.SequenceMatcher(None, na, nv, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            x, y = tia[blk.a + k], tiv[blk.b + k]
            if x - anchors[-1][0] >= 0.3 and y - anchors[-1][1] >= 0.3:
                r = (x - anchors[-1][0]) / (y - anchors[-1][1])
                if 0.8 <= r <= 1.25:
                    anchors.append((x, y))
    anchors.append((b - a, vb - va))
    if len(anchors) > 2 and anchors[-1][0] - anchors[-2][0] < 0.15:
        anchors.pop(-2)
    fc, labels = "", []
    for k in range(len(anchors) - 1):
        (x0, y0), (x1, y1) = anchors[k], anchors[k + 1]
        tempo = max(0.6, min(1.6, (x1 - x0) / max(0.05, y1 - y0)))
        fc += f"[0:a]atrim={a + x0:.4f}:{a + x1:.4f},asetpts=PTS-STARTPTS,atempo={tempo:.4f}[p{k}];"
        labels.append(f"[p{k}]")
    fc += "".join(labels) + f"concat=n={len(labels)}:v=0:a=1,apad,atrim=0:{vb - va:.4f}[a]"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", p.dir / au["file"], "-filter_complex", fc, "-map", "[a]",
            "-ar", "48000", "-ac", "2", out])
    ad.save_json(out.with_suffix(".anchors.json"), anchors)


def build(p: ad.Project, spec: dict, work: Path) -> list[dict]:
    srcs = {k: p.dir / v for k, v in spec["sources"].items()}
    segs, t = [], 0.0
    for i, s in enumerate(spec["segments"]):
        au = s.get("audio")
        va, vb = (s.get("v") or [0, None])
        if au and au.get("sync"):
            dur = frames(vb - va)
            au = {**au, "end": au["start"] + dur}
        elif au and not au.get("warp") and vb is None:
            dur = frames(au["end"] - au["start"] + s.get("tail", 0.0))
        else:
            dur = frames(vb - va)
        key = json.dumps([s.get("src"), va, vb, au, s.get("zoom"), dur], sort_keys=True, ensure_ascii=False)
        out = work / f"seg_{i:02d}.mp4"
        meta = out.with_suffix(".key")
        if not out.exists() or not meta.exists() or meta.read_text() != key:
            wav = work / f"seg_{i:02d}.wav"
            if au and au.get("warp"):
                warp_audio(p, work, au, srcs[s["src"]], va, vb, wav)
            elif au:
                lead = s.get("lead", 0.0)
                ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{au['start']:.3f}", "-to", f"{au['end']:.3f}",
                        "-i", p.dir / au["file"], "-af",
                        f"adelay={int(lead * 1000)}:all=1,afade=t=in:d=0.02,apad,atrim=0:{dur:.4f}",
                        "-ar", "48000", "-ac", "2", wav])
            else:
                ad.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{dur:.4f}", "-i",
                        "anullsrc=r=48000:cl=stereo", wav])
            z = s.get("zoom", 1.0)
            vf = (f"fps={FPS},scale={int(W * z) // 2 * 2}:{int(H * z) // 2 * 2}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},eq=brightness={spec.get('brightness', 0.03)}:saturation=1.04,format=yuv420p")
            if s.get("src"):
                have = ad.ffprobe_duration(srcs[s["src"]])
                va = min(va, max(0.0, have - dur - 0.05)) if vb is None else va
                clip = sdr(p, srcs[s["src"]], va, min(dur, have - va))
                vin = ["-i", clip]
                vf += f",tpad=stop_mode=clone:stop_duration={dur:.3f}"
            else:
                vin = ["-f", "lavfi", "-t", f"{dur:.4f}", "-i", f"color=c=black:s={W}x{H}:r={FPS}"]
            ad.run(["ffmpeg", "-y", "-v", "error", *vin, "-i", wav, "-map", "0:v", "-map", "1:a", "-vf", vf,
                    "-t", f"{dur:.4f}", "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-g", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out])
            meta.write_text(key)
        segs.append({**s, "i": i, "at": round(t, 4), "len": dur, "file": out, "who": "nakamura",
                     "v": [round(t, 4), round(t + dur, 4)]})
        t += dur
    return segs


CSS = """
@font-face {{ font-family: "Noto"; src: url("fonts/noto.ttf") format("truetype"); font-weight: 100 900; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden;
  font-family: "Hiragino Mincho ProN", "ヒラギノ明朝 ProN", serif; }}
#base {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; transform-origin: 50% 30%; }}
.layer {{ position: absolute; inset: 0; pointer-events: none; }}
.title {{ position: absolute; right: 44px; top: 150px; background: rgba(28,28,28,.78); color: #fff;
  font-size: 40px; font-weight: 600; padding: 12px 22px; letter-spacing: .02em; }}
.cap {{ position: absolute; left: 60px; right: 60px; top: 930px; display: flex; justify-content: center; }}
.blk {{ display: inline-flex; flex-direction: column; align-items: center; color: #fff; font-weight: 600;
  line-height: 1.32; letter-spacing: .02em; text-align: center;
  text-shadow: 0 0 3px rgba(0,0,0,.75), 0 0 10px rgba(0,0,0,.55), 0 3px 14px rgba(0,0,0,.5); }}
.ln {{ white-space: nowrap; }}
.big {{ font-size: 1.32em; }}
.black .blk {{ font-size: 1.05em; }}
"""


def markup(text: str) -> str:
    out = []
    for ln in text.split("/"):
        h = escape(ln)
        h = re.sub(r"\*(.+?)\*", r'<span class="big">\1</span>', h)
        out.append(f'<span class="ln">{h}</span>')
    return "".join(out)


def plain(t: str) -> str:
    return re.sub(r"[*#!]", "", t)


def compose(p: ad.Project, segs: list[dict], total: float, base: Path, audio: Path,
            hf: Path | None = None, media_start: float = 0.0) -> None:
    import shutil
    hf = hf or p.hf
    if hf.exists():
        shutil.rmtree(hf)
    (hf / "fonts").mkdir(parents=True)
    (hf / "vendor").mkdir()
    shutil.copy2(ad.STUDIO / "fonts/NotoSansJP-Variable.ttf", hf / "fonts/noto.ttf")
    shutil.copy2(ad.STUDIO / "templates/vendor/gsap.min.js", hf / "vendor/gsap.min.js")
    shutil.copy2(base, hf / "base.mp4")
    shutil.copy2(audio, hf / "voice.m4a")
    ad.save_json(hf / "hyperframes.json", {"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                                          "paths": {"assets": "assets"}})
    ad.save_json(hf / "meta.json", {"id": p.name, "name": p.name})
    title = SPEC.get("title_badge", "")
    els, js, caps = [], [], []
    if title:
        els.append(f'<div id="ttl" class="clip layer" data-start="0" data-duration="{total:.3f}" data-track-index="5">'
                   f'<div class="title">{escape(title)}</div></div>')
    for s in segs:
        ls, le = s["at"], round(s["at"] + s["len"], 3)
        if "punch" in s:
            pt = s["parts"][min(s["punch"], len(s["parts"]) - 1)]["start"]
            js.append(f'tl.fromTo("#base",{{scale:1}},{{scale:1.12,duration:0.25,ease:"power2.out"}},{pt:.3f});')
            js.append(f'tl.set("#base",{{scale:1}},{le:.3f});')
        for k, part in enumerate(s["parts"]):
            st, du = part["start"], max(0.2, part["end"] - part["start"])
            eid = f"s{s['i']}_{k}"
            txt = part["text"]
            longest = max(len(plain(x)) for x in txt.split("/"))
            fs = int(min(74 if s.get("style") == "black" else 66, (W - 140) / max(1, longest)))
            els.append(f'<div id="{eid}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                       f'data-track-index="2"><div class="cap {s.get("style", "")}"><div class="blk" '
                       f'style="font-size:{fs}px">{markup(txt)}</div></div></div>')
            caps.append({"start": st, "end": round(st + du, 3), "hook": k == 0 and s["i"] == 0,
                         "who": "nakamura", "text": plain(txt.replace("/", "\n"))})
    html = f"""<!doctype html>
<html lang="ja" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<script src="vendor/gsap.min.js"></script>
<style>{CSS.format(W=W, H=H)}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{W}" data-height="{H}">
<video id="base" src="base.mp4" muted playsinline data-start="0" data-duration="{total:.3f}" data-media-start="{media_start:.3f}" data-track-index="0"></video>
<audio id="voice" src="voice.m4a" data-start="0" data-duration="{total:.3f}" data-media-start="{media_start:.3f}" data-volume="1" data-track-index="1"></audio>
{chr(10).join(els)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""
    (hf / "index.html").write_text(html, encoding="utf-8")
    if hf == p.hf:
        ad.save_json(p.edit / "captions.json", caps)


SPEC: dict = {}


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
    # テロップの時刻：つないだ音声を文字起こしして、区間内の文字位置に合わせる
    words = ad.transcribe_whisper(audio, work / "voice_words.json")
    talk.caption_parts(segs, words)
    ad.save_json(work / "timeline.json", [{k: (str(v) if isinstance(v, Path) else v) for k, v in s.items()} for s in segs])
    talk.compose = compose  # 分割書き出しは talk の仕組みを使い、見た目だけ CR12 型に差し替える
    compose(p, segs, total, base, audio)
    raw = talk.render_parts(p, segs, total, base, audio, work, a.draft)
    final = ad.loudnorm_to_output(p, raw, suffix=tag + ("_draft" if a.draft else ""))
    ad.log(f"→ {final.relative_to(ad.STUDIO)}")


if __name__ == "__main__":
    main()
