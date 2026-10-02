#!/usr/bin/env python3
"""本人語り型（REFERENCE_STYLE 型2 / CR25）を live.json から組み立てる。

  ad live <name> [--draft]

- 実写（グリーンバック）を指定区間カット → クロマキーで背景差し替え（ぼかして奥行き）
- 後撮り音声の指定区間をつないでナレーション化（無音を詰め、atempo で尺調整）
- 寄り引きのジャンプズーム、CR25 風テロップ（黄/赤/大きい数字/縦書き/モノクロ＋紫/赤いCTA＋矢印）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ad  # noqa: E402

W, H, FPS = ad.W, ad.H, ad.FPS
SW, SH = 1440, 2560          # 合成解像度（ズーム 1.33 倍まで画質を保つ）
GAP = 0.1
ZOOMS = [1.0, 1.18, 1.32, 1.18]


def markup(text: str) -> str:
    out = []
    for ln in text.split("/"):
        h = escape(ln)
        h = re.sub(r"#(.+?)#", r'<span class="big">\1</span>', h)
        h = re.sub(r"\*(.+?)\*", r'<span class="y">\1</span>', h)
        h = re.sub(r"!(.+?)!", r'<span class="r">\1</span>', h)
        out.append(f'<div class="ln">{h}</div>')
    return "".join(out)


def wrap(text: str, maxc: int = 12) -> str:
    """'/' が無く長いテロップは、BudouX の文節境界で真ん中に近い位置で2行に分ける（記法の * ! # は保持）。"""
    if "/" in text or len(plain(text)) <= maxc:
        return text
    import budoux
    chunks = budoux.load_default_japanese_parser().parse(plain(text))
    half, acc, cut = len(plain(text)) / 2, 0, 0
    best = None
    for c in chunks[:-1]:
        acc += len(c)
        if best is None or abs(acc - half) < abs(best - half):
            best = acc
    cut = best or int(half)
    out, n, done = "", 0, False  # 記号を飛ばして数え、cut 文字目の直前に '/' を入れる
    for ch in text:
        if not done and n == cut:
            out += "/"
            done = True
        if ch not in "*!#":
            n += 1
        out += ch
    # 強調記号の途中で改行した場合は、行ごとに記号を閉じ直す
    lines = out.split("/")
    fixed, open_mark = [], ""
    for ln in lines:
        ln = open_mark + ln
        open_mark = ""
        for m in "*!#":
            if ln.count(m) % 2:
                ln += m
                open_mark = m
        fixed.append(ln)
    return "/".join(fixed)


def plain(t: str) -> str:
    return re.sub(r"[*!#/|]", "", t)


def fit(text: str, base: int, width: int, big: float = 1.35) -> int:
    def units(line):
        n, inbig = 0.0, False
        for c in line:
            if c == "#":
                inbig = not inbig
                continue
            if c in "*!":
                continue
            n += (0.55 if c.isascii() else 1.0) * (big if inbig else 1.0)
        return n
    return int(min(base, width / max(max(units(l) for l in text.split("/")) + 0.5, 1)))


def kept_ranges(cuts: list, dur: float) -> list[tuple[float, float]]:
    out, t = [], 0.0
    for a, b in sorted(cuts):
        if a > t + 0.05:
            out.append((t, min(a, dur)))
        t = max(t, b)
    if t < dur - 0.3:
        out.append((t, dur))
    return out


def build_audio(p: ad.Project, spec: dict, work: Path) -> tuple[list[dict], float]:
    envs, lines, t = {}, [], 0.0
    tempo = spec.get("atempo", 1.0)
    for i, l in enumerate(spec["lines"], 1):
        src = p.dir / "input" / l["src"]
        if src not in envs:
            envs[src] = ad.audio_envelope(src)
        s, e = ad.snap_to_audio(*envs[src], l["start"], l["end"])
        out = work / f"line_{i:02d}.wav"
        af = ("silenceremove=start_periods=1:start_threshold=-42dB,"
              "silenceremove=stop_periods=-1:stop_duration=0.22:stop_threshold=-42dB:stop_silence=0.1,"
              "areverse,silenceremove=start_periods=1:start_threshold=-42dB,areverse,"
              f"atempo={tempo},afade=t=in:d=0.02,areverse,afade=t=in:d=0.03,areverse")
        ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", src, "-af", af,
                "-ac", "1", "-ar", "48000", out])
        d = ad.ffprobe_duration(out)
        lines.append({**l, "i": i, "wav": str(out), "at": round(t, 3), "len": round(d, 3)})
        t += d + GAP
    total = round(round((t - GAP + 0.6) * FPS) / FPS, 4)
    inputs, filt = [], []
    for k, l in enumerate(lines):
        inputs += ["-i", l["wav"]]
        ms = int(l["at"] * 1000)
        filt.append(f"[{k}:a]adelay={ms}|{ms}[a{k}]")
    filt.append("".join(f"[a{k}]" for k in range(len(lines))) +
                f"amix=inputs={len(lines)}:normalize=0,apad=whole_dur={total}[out]")
    ad.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
            "-ac", "2", "-ar", "48000", "-t", f"{total}", work / "narration.wav"])
    return lines, total


def part_times(lines: list[dict], words: list[dict]) -> None:
    """各行を '|' で区切ったテロップに分け、再文字起こしの文字位置で開始時刻を割り当てる。"""
    for l in lines:
        parts = l["telop"].split("|") if l.get("style") not in ("tate", "hook", "red", "mono") else [l["telop"]]
        s, e = l["at"], l["at"] + l["len"]
        toks = [w for w in words if s - 0.15 <= w["start"] <= e]
        text, times = ad.char_times(toks) if toks else ("", [])
        keep = [k for k, c in enumerate(text) if c not in ad.PUNCT]
        nt = len(keep)
        total_chars = sum(len(ad.norm(plain(x))) for x in parts) or 1
        acc, out = 0, []
        for x in parts:
            frac = acc / total_chars
            st = times[keep[min(nt - 1, int(frac * nt))]] if nt else s + frac * (e - s)
            out.append({"text": x, "start": max(s, round(st, 3)) if acc else s})
            acc += len(ad.norm(plain(x)))
        for k, o in enumerate(out):
            o["end"] = out[k + 1]["start"] if k + 1 < len(out) else round(e + GAP, 3)
        l["parts"] = out


def build_video(p: ad.Project, spec: dict, total: float, work: Path) -> Path:
    src = p.dir / spec["video"]
    dur = ad.ffprobe_duration(src)
    keeps = kept_ranges(spec["cuts"], dur)
    kept_total = sum(b - a for a, b in keeps)
    f = min(1.0, total / kept_total)
    ad.log(f"実写: 使用区間 {len(keeps)} 個・計 {kept_total:.1f} 秒 → 各区間の中央 {f * 100:.0f}% を使用")
    bg = p.dir / spec["background"]
    segs, acc = [], 0.0
    for k, (a, b) in enumerate(keeps):
        want = (b - a) * f
        if k == len(keeps) - 1:
            want = total - acc
        want = round(round(want * FPS) / FPS, 4)
        st = a + ((b - a) - want) / 2
        sdr = work / f"sdr_{k:02d}.mp4"
        # iPhone の HDR(HLG) は macOS の avconvert で SDR に（ffmpeg に zscale が無いため）
        ad.run(["avconvert", "-s", src, "-o", sdr, "-p", "Preset3840x2160", "--start", f"{st:.3f}",
                "--duration", f"{want + 0.2:.3f}", "--replace"], stdout=subprocess.DEVNULL)
        out = work / f"seg_{k:02d}.mp4"
        fc = (f"[1:v]scale={SW}:{SH}:force_original_aspect_ratio=increase,crop={SW}:{SH},gblur=sigma=9,"
              f"eq=brightness=0.02:saturation=1.08,colorbalance=rs=0.03:bs=-0.02[bg];"
              f"[0:v]fps={FPS},scale={SW}:{SH},format=yuva444p,"
              f"chromakey=color={spec.get('green', '0x78B23A')}:similarity=0.08:blend=0.04,"
              f"despill=type=green:mix=0.6:expand=0.1,eq=brightness=0.04:contrast=1.05:saturation=1.06[fg];"
              f"[bg][fg]overlay=0:0:shortest=1,format=yuv420p[v]")
        ad.run(["ffmpeg", "-y", "-v", "error", "-i", sdr, "-loop", "1", "-i", bg, "-filter_complex", fc,
                "-map", "[v]", "-t", f"{want:.4f}", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "17", out])
        sdr.unlink()
        segs.append(out)
        acc += want
    (work / "list.txt").write_text("".join(f"file '{x.name}'\n" for x in segs))
    joined = work / "joined.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", work / "list.txt", "-c", "copy", joined])
    return finalize_base(joined, work / "base.mp4")


def finalize_base(src: Path, base: Path) -> Path:
    """HyperFrames のシーク用にキーフレームを1秒ごとに入れ、末尾を1秒だけ静止で延ばす。"""
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", "tpad=stop_mode=clone:stop_duration=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-g", str(FPS), "-keyint_min", str(FPS),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", base])
    return base


def compose(p: ad.Project, spec: dict, lines: list[dict], total: float, base: Path, narration: Path) -> None:
    hf = p.hf
    if hf.exists():
        shutil.rmtree(hf)
    (hf / "fonts").mkdir(parents=True)
    (hf / "vendor").mkdir()
    shutil.copy2(ad.STUDIO / "fonts/NotoSansJP-Variable.ttf", hf / "fonts/noto.ttf")
    shutil.copy2(ad.STUDIO / "fonts/MPLUS1p-Black.ttf", hf / "fonts/mplus.ttf")
    shutil.copy2(ad.STUDIO / "templates/vendor/gsap.min.js", hf / "vendor/gsap.min.js")
    shutil.copy2(base, hf / "base.mp4")
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", narration, "-c:a", "aac", "-b:a", "192k", hf / "voice.m4a"])
    ad.make_sfx(hf / "sfx")
    pop = next((hf / "sfx").glob("pop.*")).name
    ad.save_json(hf / "hyperframes.json", {"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                                          "paths": {"assets": "assets"}})
    ad.save_json(hf / "meta.json", {"id": p.name, "name": p.name})

    zone = W - 160
    els, js, caps, audio = [], [], [], []
    zi = 0
    for l in lines:
        sty = l.get("style", "normal")
        for k, part in enumerate(l["parts"]):
            st, du = part["start"], max(0.2, part["end"] - part["start"])
            eid = f"t{l['i']}_{k}"
            z = 1.32 if sty in ("hook", "red", "mono") else ZOOMS[zi % len(ZOOMS)]
            zi += 1
            js.append(f'tl.set("#base",{{scale:{z}}},{st:.3f});')
            txt = wrap(part["text"]) if sty in ("normal", "cta") else part["text"]
            if sty == "tate":
                cols = txt.split("/")
                fs = int(min(96, 1250 / (max(len(plain(c)) for c in cols) + 0.6)))
                html = markup(txt)
                els.append(f'<div id="{eid}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                           f'data-track-index="2"><div class="tate" style="font-size:{fs}px">{html}</div></div>')
                js.append(f'tl.fromTo("#{eid} .ln",{{opacity:0,y:-30}},{{opacity:1,y:0,duration:0.25,stagger:0.3}},{st:.3f});')
            else:
                base_fs = {"hook": 96, "red": 92, "mono": 88}.get(sty, 66)
                fs = fit(txt, base_fs, zone)
                cls = {"hook": "cap hook", "red": "cap hook", "mono": "cap mono"}.get(sty, "cap")
                els.append(f'<div id="{eid}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                           f'data-track-index="2"><div class="{cls}" style="font-size:{fs}px">{markup(txt)}</div></div>')
                if sty in ("hook", "red"):
                    js.append(f'tl.fromTo("#{eid} .cap",{{scale:0.7,opacity:0}},{{scale:1,opacity:1,duration:0.2,'
                              f'ease:"back.out(2)"}},{st:.3f});')
            caps.append({"start": st, "end": round(st + du, 3), "hook": sty == "hook", "text": plain(txt.replace("/", "\n"))})
        ls, le = l["at"], round(l["at"] + l["len"] + GAP, 3)
        if sty == "mono":
            js.append(f'tl.set("#base",{{filter:"grayscale(1) contrast(1.1)"}},{ls:.3f});')
            js.append(f'tl.set("#base",{{filter:"none"}},{le:.3f});')
        if sty == "cta":
            cf = fit(l["cta"], 54, zone - 80)
            els.append(f'<div id="cta{l["i"]}" class="clip layer" data-start="{ls:.3f}" data-duration="{le - ls:.3f}" '
                       f'data-track-index="4"><div class="ctabox" style="font-size:{cf}px">{markup(l["cta"])}</div>'
                       f'<div class="arrows"><span>↓</span><span>↓</span><span>↓</span></div></div>')
            js.append(f'tl.fromTo("#cta{l["i"]} .ctabox",{{scale:0.75,opacity:0}},{{scale:1,opacity:1,duration:0.25,'
                      f'ease:"back.out(1.8)"}},{ls:.3f});')
            js.append(f'tl.fromTo("#cta{l["i"]} .arrows span",{{y:0}},{{y:16,duration:0.3,yoyo:true,'
                      f'repeat:{max(1, int((le - ls) / 0.6))},stagger:0.08,ease:"sine.inOut"}},{ls + 0.2:.3f});')
            audio.append(f'<audio id="pop{l["i"]}" src="sfx/{pop}" data-start="{ls:.3f}" data-duration="0.16" '
                         f'data-volume="0.35" data-track-index="{5 + l["i"] % 2}"></audio>')

    disc = escape(spec.get("disclaimer", ""))
    html = f"""<!doctype html>
<html lang="ja" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<script src="vendor/gsap.min.js"></script>
<style>
@font-face {{ font-family: "Noto"; src: url("fonts/noto.ttf") format("truetype"); font-weight: 100 900; }}
@font-face {{ font-family: "MPlus"; src: url("fonts/mplus.ttf") format("truetype"); font-weight: 900; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; font-family: "Noto", sans-serif; }}
#base {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; transform-origin: 50% 30%; }}
.layer {{ position: absolute; inset: 0; pointer-events: none; }}
.cap {{ position: absolute; left: 80px; right: 80px; top: 1010px; text-align: center; color: #fff; font-weight: 900;
  line-height: 1.32; letter-spacing: 0.01em; -webkit-text-stroke: 9px #111; paint-order: stroke fill;
  text-shadow: 0 4px 10px rgba(0,0,0,.45); }}
.cap.hook {{ top: 930px; font-family: "MPlus", sans-serif; -webkit-text-stroke: 12px #111; }}
.cap.mono {{ top: 980px; color: #B57CFF; font-family: "MPlus", sans-serif; -webkit-text-stroke: 11px #111; }}
.ln {{ white-space: nowrap; }}
.y {{ color: #FFE14D; }}
.r {{ color: #FF2E2E; }}
.big {{ color: #FFE14D; font-size: 1.35em; }}
.tate {{ position: absolute; right: 60px; top: 280px; height: 1320px;
  writing-mode: vertical-rl; color: #FFE14D; font-family: "MPlus", sans-serif; font-weight: 900; line-height: 1.15;
  -webkit-text-stroke: 12px #111; paint-order: stroke fill; text-shadow: 0 4px 12px rgba(0,0,0,.5); }}
.tate .ln {{ white-space: nowrap; }}
.ctabox {{ position: absolute; left: 110px; right: 110px; top: 1230px; background: #E8333A; color: #fff;
  font-family: "MPlus", sans-serif; text-align: center; line-height: 1.3; padding: 24px 18px; border-radius: 22px;
  border: 5px solid #fff; box-shadow: 0 10px 28px rgba(0,0,0,.35); }}
.ctabox .y {{ color: #FFF15A; }}
.arrows {{ position: absolute; left: 0; right: 0; top: 1440px; display: flex; justify-content: center; gap: 70px;
  color: #FFE14D; font-size: 90px; font-weight: 900; -webkit-text-stroke: 8px #111; paint-order: stroke fill; }}
.arrows span {{ display: inline-block; }}
#disc {{ position: absolute; left: 60px; top: 236px; color: rgba(255,255,255,.95); font-size: 24px; font-weight: 600;
  text-shadow: 0 1px 4px rgba(0,0,0,.9); }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{W}" data-height="{H}">
<video id="base" src="base.mp4" muted playsinline data-start="0" data-duration="{total:.3f}" data-track-index="0"></video>
<audio id="voice" src="voice.m4a" data-start="0" data-duration="{total:.3f}" data-volume="1" data-track-index="1"></audio>
{chr(10).join(audio)}
{chr(10).join(els)}
<div id="disclayer" class="clip layer" data-start="0" data-duration="{total:.3f}" data-track-index="7"><div id="disc">{disc}</div></div>
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
    ad.save_json(p.edit / "captions.json", caps)


def cmd_live(a) -> None:
    p = ad.Project(a.name)
    spec = ad.load_json(p.dir / "live.json")
    work = p.edit / "live"
    work.mkdir(parents=True, exist_ok=True)
    lines, total = build_audio(p, spec, work)
    ad.log(f"ナレーション {len(lines)} 行・{total:.1f} 秒（{spec.get('atempo', 1.0)} 倍速）")
    words = ad.transcribe_whisper(work / "narration.wav", work / "narration_words.json")
    part_times(lines, words)
    ad.save_json(work / "timeline.json", [{k: v for k, v in l.items() if k != "wav"} for l in lines])
    base = work / "base.mp4"
    if a.reuse_video and base.exists() and ad.ffprobe_duration(base) >= total - 0.05:
        ad.log("実写の合成は前回分を再利用")
        if not (work / "joined.mp4").exists():  # 旧形式の base はキーフレームを入れ直す
            base.rename(work / "joined.mp4")
            finalize_base(work / "joined.mp4", base)
    else:
        base = build_video(p, spec, total, work)
    compose(p, spec, lines, total, base, work / "narration.wav")
    lint = subprocess.run([ad.HF_BIN, "lint", str(p.hf)], capture_output=True, text=True)
    print((lint.stdout or lint.stderr).strip().splitlines()[-1])
    ad.cmd_render(argparse.Namespace(name=a.name, draft=a.draft))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--reuse-video", action="store_true")
    cmd_live(ap.parse_args())
