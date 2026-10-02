#!/usr/bin/env python3
"""ナレーション＋Bロール型（references/REFERENCE_STYLE.md）の動画を shots.json から組み立てる。

  ad story <name> [--draft]

projects/<name>/shots.json … 1行＝1カットの台本（telop: テロップ / read: 読み上げ / broll: broll/ のファイル名 /
  style: normal|hook|card|cta / label: 見出しラベル / cta: CTAボックスの文言）
projects/<name>/broll/     … Bロール映像
projects/<name>/narration/ … 本番ナレーション（shot_01.wav … を置くと仮の合成音声の代わりに使う）
projects/<name>/bgm.*      … BGM（なければ仮の合成BGM）
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
import ad  # noqa: E402  共通ユーティリティ（ffprobe, loudnorm, QA など）

W, H, FPS = ad.W, ad.H, ad.FPS
GAP, CARD_GAP, TAIL = 0.08, 0.3, 0.9


def markup(text: str) -> str:
    """/ → 改行、*語* → 黄色、!語! → 赤。"""
    lines = []
    for ln in text.split("/"):
        h = escape(ln)
        h = re.sub(r"\*(.+?)\*", r'<span class="y">\1</span>', h)
        h = re.sub(r"!(.+?)!", r'<span class="r">\1</span>', h)
        lines.append(f'<div class="ln">{h}</div>')
    return "".join(lines)


def plain(text: str) -> str:
    return re.sub(r"[*!/]", "", text)


def visible_len(line: str) -> float:
    s = plain(line)
    return sum(0.55 if c.isascii() else 1.0 for c in s)


def fit(text: str, base: int, width: int) -> int:
    longest = max(visible_len(l) for l in text.split("/"))
    return int(min(base, width / max(longest + 0.4, 1)))


def tts(text: str, voice: str, rate: int, out: Path) -> float:
    aiff = out.with_suffix(".aiff")
    ad.run(["say", "-v", voice, "-r", str(rate), "-o", aiff, text])
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", aiff, "-ac", "1", "-ar", "48000", out])
    aiff.unlink()
    # 前後の無音を詰める（say は末尾に余白が入る）
    trimmed = out.with_name(out.stem + "_t.wav")
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", out, "-af",
            "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB,areverse", trimmed])
    trimmed.replace(out)
    return ad.ffprobe_duration(out)


def synth_bgm(out: Path, dur: float) -> None:
    """仮BGM：C-Am-F-G のやわらかいパッド＋8分の脈動（著作権フリーの自作）。本番は差し替え前提。"""
    chords = ["261.6,329.6,392.0", "220.0,261.6,329.6", "174.6,220.0,261.6", "196.0,246.9,293.7"]

    def tone(i):
        f = chords[i].split(",")
        return "+".join(f"sin(2*PI*{x}*t)+0.3*sin(2*PI*{float(x) * 2}*t)" for x in f)
    expr = "+".join(f"if(eq(floor(mod(t,8)/2),{i}),{tone(i)},0)" for i in range(4))
    expr = f"0.07*({expr})*(0.55+0.45*exp(-5*mod(t,0.5)))+0.05*sin(2*PI*65.4*t)*exp(-8*mod(t,1))"
    ad.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={dur:.2f}",
            "-af", "lowpass=f=2400,afade=t=in:d=0.8,afade=t=out:st=" + f"{max(0, dur - 1.5):.2f}:d=1.5",
            "-ac", "2", out])


def cmd_story(a) -> None:
    p = ad.Project(a.name)
    spec = ad.load_json(p.dir / "shots.json")
    shots = spec["shots"]
    work = p.edit / "story"
    (work / "voice").mkdir(parents=True, exist_ok=True)
    br = ad.brand()

    # 1) ナレーション（本番音声があれば優先、なければ仮の合成音声）
    t, timeline = 0.0, []
    for i, s in enumerate(shots, 1):
        real = p.dir / "narration" / f"shot_{i:02d}.wav"
        wav = work / "voice" / f"shot_{i:02d}.wav"
        if real.exists():
            ad.run(["ffmpeg", "-y", "-v", "error", "-i", real, "-ac", "1", "-ar", "48000", wav])
            vd = ad.ffprobe_duration(wav)
        else:
            vd = tts(s.get("read") or plain(s["telop"]), spec.get("voice", "Kyoko"), spec.get("rate", 210), wav)
        gap = CARD_GAP if s.get("style") == "card" else GAP
        if i == len(shots):
            gap = TAIL
        dur = vd + gap + (0.15 if s.get("style") == "card" else 0)
        dur = round(round(dur * FPS) / FPS, 4)  # フレーム単位にそろえ、映像とテロップのズレを防ぐ
        timeline.append({**s, "i": i, "start": round(t, 3), "dur": dur, "voice": str(wav),
                         "voice_at": round(t + (0.12 if s.get("style") == "card" else 0.02), 3), "voice_dur": vd})
        t += dur
    total = round(t, 3)
    ad.log(f"ナレーション {len(shots)} 本・合計 {total:.1f} 秒")

    # 2) 映像：カットごとに Bロールを切り出して 1080×1920 に（カードは黒）
    segs = []
    for s in timeline:
        out = work / f"seg_{s['i']:02d}.mp4"
        if s.get("broll"):
            src = next((p.dir / "broll").glob(s["broll"] + ".*"))
            cd = ad.ffprobe_duration(src)
            ss = max(0.0, min(cd * 0.25, cd - s["dur"] - 0.1))
            loop = ["-stream_loop", "-1"] if cd < s["dur"] + 0.2 else []
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},"
                  f"eq=saturation=1.05:contrast=1.03")
            ad.run(["ffmpeg", "-y", "-v", "error", *loop, "-ss", f"{ss:.2f}", "-i", src, "-t", f"{s['dur']:.3f}",
                    "-an", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", out])
        else:
            ad.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}",
                    "-t", f"{s['dur']:.3f}", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", out])
        segs.append(out)
    (work / "list.txt").write_text("".join(f"file '{x.name}'\n" for x in segs))
    base = work / "base.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", work / "list.txt", "-c", "copy", base])

    # 3) 音：声・効果音・BGM を先に 1 本へ混ぜる（BGM は声の下で -12dB 程度にダッキング）
    sfxdir = work / "sfx"
    ad.make_sfx(sfxdir)
    events = [(s["voice"], s["voice_at"], 1.0) for s in timeline]
    for s in timeline:  # 効果音は見出し・CTA の出現だけ（付けすぎない）
        if s.get("label") or s.get("style") == "cta":
            events.append((str(next(sfxdir.glob("pop.*"))), s["start"], 0.35))
    events.append((str(next(sfxdir.glob("whoosh.*"))), 0.0, 0.3))
    bgm_src = next((f for f in p.dir.glob("bgm.*")), None)
    bgm = work / "bgm.wav"
    if bgm_src:
        ad.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", bgm_src, "-t", f"{total:.2f}",
                "-ac", "2", "-ar", "48000", "-af", f"afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5", bgm])
    else:
        synth_bgm(bgm, total)
    inputs, filters = [], []
    for k, (f, at, vol) in enumerate(events):
        inputs += ["-i", f]
        filters.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={vol},"
                       f"adelay={int(at * 1000)}|{int(at * 1000)}[e{k}]")
    n = len(events)
    filters.append("".join(f"[e{k}]" for k in range(n)) + f"amix=inputs={n}:normalize=0:duration=longest,"
                   f"apad=whole_dur={total:.3f}[fg]")
    filters.append(f"[{n}:a]volume=0.55[bg]")
    filters.append("[fg]asplit=2[fg1][fg2]")
    filters.append("[bg][fg2]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[bgd]")
    filters.append("[fg1][bgd]amix=inputs=2:normalize=0:duration=first[out]")
    mix = work / "mix.wav"
    ad.run(["ffmpeg", "-y", "-v", "error", *inputs, "-i", bgm, "-filter_complex", ";".join(filters),
            "-map", "[out]", "-t", f"{total:.3f}", "-ar", "48000", mix])

    # 4) HyperFrames：テロップ・フック・ラベル・カード・CTA・打消し表示
    hf = p.hf
    if hf.exists():
        shutil.rmtree(hf)
    (hf / "fonts").mkdir(parents=True)
    (hf / "vendor").mkdir()
    shutil.copy2(ad.STUDIO / "fonts/NotoSansJP-Variable.ttf", hf / "fonts/noto.ttf")
    shutil.copy2(ad.STUDIO / "fonts/MPLUS1p-Black.ttf", hf / "fonts/mplus.ttf")
    shutil.copy2(ad.STUDIO / "templates/vendor/gsap.min.js", hf / "vendor/gsap.min.js")
    shutil.copy2(base, hf / "base.mp4")
    shutil.copy2(mix, hf / "mix.wav")
    ad.save_json(hf / "hyperframes.json", {"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                                          "paths": {"assets": "assets"}})
    ad.save_json(hf / "meta.json", {"id": p.name, "name": p.name})

    zone = W - 2 * 90
    els, js, caps = [], [], []
    # 見出しラベルは、次のラベル・カード・CTA が来るまで出し続ける
    label, label_start = None, 0.0

    def flush_label(end: float):
        if label:
            k = len(els)
            els.append(f'<div id="lb{k}" class="clip layer" data-start="{label_start:.3f}" '
                       f'data-duration="{end - label_start:.3f}" data-track-index="3"><div class="label">'
                       f'{escape(label)}</div></div>')
            js.append(f'tl.fromTo("#lb{k} .label",{{scale:0.6,opacity:0}},{{scale:1,opacity:1,duration:0.25,'
                      f'ease:"back.out(2)"}},{label_start:.3f});')

    for s in timeline:
        st, du, sty = s["start"], s["dur"], s.get("style", "normal")
        if s.get("label") or sty in ("card", "cta", "hook"):
            flush_label(st)
            label = None
        if s.get("label"):
            label, label_start = s["label"], st
        tel = s["telop"]
        if sty == "hook":
            fs = fit(tel, 96, W - 80)
            els.append(f'<div id="s{s["i"]}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                       f'data-track-index="2"><div class="hook" style="font-size:{fs}px">{markup(tel)}</div></div>')
            js.append(f'tl.fromTo("#s{s["i"]} .hook",{{scaleY:0}},{{scaleY:1,duration:0.18,ease:"power2.out"}},{st:.3f});')
        elif sty == "card":
            fs = fit(tel, 72, zone)
            els.append(f'<div id="s{s["i"]}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                       f'data-track-index="2"><div class="card" style="font-size:{fs}px">{markup(tel)}</div></div>')
            js.append(f'tl.fromTo("#s{s["i"]} .ln",{{opacity:0,y:16}},{{opacity:1,y:0,duration:0.3,stagger:0.35}},{st + 0.05:.3f});')
        else:
            fs = fit(tel, 70, zone)
            els.append(f'<div id="s{s["i"]}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                       f'data-track-index="2"><div class="cap" style="font-size:{fs}px">{markup(tel)}</div></div>')
            if sty == "cta":
                cf = fit(s["cta"], 64, zone - 60)
                els.append(f'<div id="c{s["i"]}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                           f'data-track-index="4"><div class="ctabox" style="font-size:{cf}px">{markup(s["cta"])}'
                           f'<div class="arrow">▼</div></div></div>')
                js.append(f'tl.fromTo("#c{s["i"]} .ctabox",{{scale:0.7,opacity:0}},{{scale:1,opacity:1,duration:0.3,'
                          f'ease:"back.out(1.8)"}},{st:.3f});')
                js.append(f'tl.fromTo("#c{s["i"]} .arrow",{{y:0}},{{y:14,duration:0.35,yoyo:true,repeat:{int(du / 0.7)},'
                          f'ease:"sine.inOut"}},{st + 0.3:.3f});')
        caps.append({"start": st, "end": round(st + du, 3), "hook": sty == "hook",
                     "text": plain(tel).replace("/", "\n") if "/" not in tel else "\n".join(plain(x) for x in tel.split("/"))})
    flush_label(total)

    disc = escape(spec.get("disclaimer", "")).replace("\n", "<br>")
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
#base {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; }}
.layer {{ position: absolute; inset: 0; pointer-events: none; }}
.cap {{ position: absolute; left: 90px; right: 90px; top: 1000px; text-align: center; color: #fff;
  font-weight: 800; line-height: 1.35; letter-spacing: 0.02em;
  -webkit-text-stroke: 7px rgba(0,0,0,.75); paint-order: stroke fill;
  text-shadow: 0 0 12px rgba(0,0,0,.8), 0 4px 8px rgba(0,0,0,.9); }}
.ln {{ white-space: nowrap; }}
.y {{ color: #FFE14D; }}
.r {{ color: #FF3B30; }}
.hook {{ position: absolute; left: 0; right: 0; top: 700px; background: #000; padding: 36px 30px;
  text-align: center; color: #fff; font-family: "MPlus", sans-serif; font-weight: 900; line-height: 1.3; }}
.hook .y {{ color: #FFE600; }}
.card {{ position: absolute; left: 90px; right: 90px; top: 50%; transform: translateY(-50%); text-align: center;
  color: #fff; font-weight: 800; line-height: 1.55; }}
.label {{ position: absolute; left: 50%; top: 880px; transform: translateX(-50%); white-space: nowrap;
  background: #E9A6E8; color: #fff; font-weight: 900; font-size: 46px; padding: 14px 40px; border-radius: 999px;
  text-shadow: 0 2px 4px rgba(120,40,120,.6); box-shadow: 0 6px 18px rgba(0,0,0,.25); }}
.ctabox {{ position: absolute; left: 110px; right: 110px; top: 560px; background: #fff; color: #111;
  font-family: "MPlus", sans-serif; font-weight: 900; text-align: center; line-height: 1.3; padding: 34px 20px 22px;
  border-radius: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.35); }}
.ctabox .y {{ color: #06C755; }}
.ctabox .arrow {{ color: #06C755; font-size: 44px; margin-top: 6px; }}
#disc {{ position: absolute; left: 60px; top: 236px; color: rgba(255,255,255,.92); font-size: 25px; line-height: 1.45;
  font-weight: 500; text-shadow: 0 1px 3px rgba(0,0,0,.9); }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{W}" data-height="{H}">
<video id="base" src="base.mp4" muted playsinline data-start="0" data-duration="{total:.3f}" data-track-index="0"></video>
<audio id="mix" src="mix.wav" data-start="0" data-duration="{total:.3f}" data-volume="1" data-track-index="1"></audio>
{chr(10).join(els)}
<div id="disclayer" class="clip layer" data-start="0" data-duration="{total:.3f}" data-track-index="5"><div id="disc">{disc}</div></div>
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
    ad.save_json(work / "timeline.json", [{k: v for k, v in s.items() if k != "voice"} for s in timeline])
    lint = subprocess.run([ad.HF_BIN, "lint", str(hf)], capture_output=True, text=True)
    print((lint.stdout or lint.stderr).strip().splitlines()[-1])
    ad.log(f"コンポジション生成（{len(shots)} カット・{total:.1f} 秒）→ レンダリング")
    ad.cmd_render(argparse.Namespace(name=a.name, draft=a.draft))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--draft", action="store_true")
    cmd_story(ap.parse_args())
