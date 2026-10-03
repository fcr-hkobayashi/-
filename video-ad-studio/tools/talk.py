#!/usr/bin/env python3
"""対話・本人語り型（REFERENCE_STYLE 型2 / CR25）を edit.json から組み立てる。元動画の音声を使う。

  ad talk <name> [--draft] [--reuse-video]

edit.json の segments（元動画の使用区間）を順につなぐ。
- who: nakamura … 元の音声を使う / satsuei … 撮影者の声。音声はミュートし、余白（尺）とテロップだけ残す
- グリーンバックはクロマキーで指定背景に差し替え（HDR は avconvert で SDR 化）
- テロップは CR25 準拠：太いゴシック・白＋やわらかい影（太フチなし）・2行は左右にずらす・
  強調は黄、数字は大きく、赤、モノクロ＋紫、撮影者の言葉は金帯の縦書き、キーメッセージは黄の縦書き、赤いCTA＋矢印
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ad  # noqa: E402

W, H, FPS = ad.W, ad.H, ad.FPS
SW, SH = 1440, 2560


def markup(text: str) -> str:
    out = []
    for ln in text.split("/"):
        h = escape(ln)
        h = re.sub(r"#(.+?)#", r'<span class="big">\1</span>', h)
        h = re.sub(r"\*(.+?)\*", r'<span class="y">\1</span>', h)
        h = re.sub(r"!(.+?)!", r'<span class="r">\1</span>', h)
        out.append(f'<div class="ln">{h}</div>')
    return "".join(out)


def plain(t: str) -> str:
    return re.sub(r"[*!#/|]", "", t)


def units(line: str) -> float:
    n, big = 0.0, False
    for c in line:
        if c == "#":
            big = not big
            continue
        if c in "*!":
            continue
        n += (0.58 if c.isascii() else 1.0) * (1.45 if big else 1.0)
    return n


def fit(text: str, base: int, width: int) -> int:
    return int(min(base, width / (max(units(l) for l in text.split("/")) + 0.3)))


def frames(t: float) -> float:
    return round(round(t * FPS) / FPS, 4)


FG_SCALE, HEAD_Y = 1.15, 0.16   # 人物の固定構図：1.15倍・頭頂を画面上から16%に（人物＋机で画面の約2/3）
SRC_HEAD_Y = 0.20                # 元映像（三脚固定）での頭頂の位置


def sdr_clip(src: Path, a: float, dur: float, cache: Path) -> Path:
    """iPhone の HDR を avconvert で SDR 4K に。区間ごとにキャッシュ（背景違いで使い回す）。"""
    out = cache / f"sdr_{a:.2f}_{dur:.2f}.mp4"
    if not out.exists():
        ad.run(["avconvert", "-s", src, "-o", out, "-p", "Preset3840x2160", "--start", f"{a:.3f}",
                "--duration", f"{dur + 0.25:.3f}", "--replace"], stdout=subprocess.DEVNULL)
    return out


def bg_filter(bg: dict, bg_size: tuple[int, int]) -> str:
    """背景を縦長キャンバスに配置。fit=natural は拡大せずに下端合わせ（物の大きさを実寸に近く保つ）。
    blur=0 ならぼかさない。crop_top で上部（透かし等）を落とす。"""
    blur = bg.get("blur", 2.5)
    tail = (f",gblur=sigma={blur}" if blur else "") + f",eq=brightness={bg.get('brightness', 0.02)}:saturation=1.03[bg];"
    if bg.get("fit") == "natural":
        import math
        w, h = bg_size
        sc = max(SW / w, SH / h) + 0.002
        sw, sh = math.ceil(w * sc), math.ceil(h * sc)
        x = int(min(max(bg.get("vx", 0.5) * sw - SW / 2, 0), sw - SW))
        return f"[1:v]scale={sw}:{sh}:flags=lanczos,crop={SW}:{SH}:{x}:{sh - SH}" + tail
    ct = bg.get("crop_top", 0.0)
    return (f"[1:v]crop=iw:ih*{1 - ct:.3f}:0:ih*{ct:.3f},scale={SW}:{SH}:force_original_aspect_ratio=increase,"
            f"crop={SW}:{SH}" + tail)


def head_pos(clip: Path, at_end: bool, green: str) -> tuple[float, float]:
    """クロマキーの切り抜きから頭頂の高さと頭の左右中心を測る（画面に対する割合）。"""
    w, h = 270, 480
    seek = ["-sseof", "-0.12"] if at_end else ["-ss", "0.05"]
    raw = subprocess.run(["ffmpeg", "-v", "error", *seek, "-i", str(clip), "-frames:v", "1", "-vf",
                          f"scale={w}:{h},format=yuva444p,chromakey=color={green}:similarity=0.08:blend=0.04,alphaextract",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    rows = [[x for x in range(w) if raw[y * w + x] > 128] for y in range(h)]
    top = next(y for y in range(h) if len(rows[y]) > 8)
    band = [x for y in range(top, min(h, top + 60)) for x in rows[y]]
    return top / h, sum(band) / len(band) / w


def align_offsets(sdrs: list[Path], green: str, pull: float = 0.1, ylim: float = 0.02,
                  xlim: float = 0.075) -> list[tuple[float, float]]:
    """カクカク対策：各カットの頭の位置を、直前のカットの終わりの位置にそろえるずらし量（画面に対する割合）。
    ずれが積み重ならないよう、全体の中央値へ pull の割合で引き戻す。
    上下は机のずれが目立たないよう ±ylim まで、左右は人物の映像のはみ出し幅（±xlim）まで。"""
    import statistics
    st = [head_pos(f, False, green) for f in sdrs]
    en = [head_pos(f, True, green) for f in sdrs]
    my = statistics.median((a[0] + b[0]) / 2 for a, b in zip(st, en))
    mx = statistics.median((a[1] + b[1]) / 2 for a, b in zip(st, en))
    offs: list[tuple[float, float]] = []
    for i in range(len(sdrs)):
        mean_y, mean_x = (st[i][0] + en[i][0]) / 2, (st[i][1] + en[i][1]) / 2
        if i == 0:
            oy, ox = my - mean_y, mx - mean_x
        else:
            ty, tx = en[i - 1][0] + offs[-1][0], en[i - 1][1] + offs[-1][1]
            oy = (1 - pull) * (ty - st[i][0]) + pull * (my - mean_y)
            ox = (1 - pull) * (tx - st[i][1]) + pull * (mx - mean_x)
        offs.append((max(-ylim, min(ylim, oy)), max(-xlim, min(xlim, ox))))
    return offs


SATSUEI_CHAIN = ("highpass=f=90,afftdn=nr=10:nf=-55,equalizer=f=250:t=q:w=1.2:g=-2,"
                 "equalizer=f=3200:t=q:w=1:g=2,acompressor=threshold=-22dB:ratio=3:attack=8:release=160,"
                 "aecho=0.85:0.5:22|41:0.10|0.06")  # カメラの後ろにいる距離感を少しだけ足す


def satsuei_clip(p: ad.Project, spec: dict, s: dict, work: Path) -> tuple[Path, float]:
    """後撮りの撮影者の声：指定区間を切り出し → ノイズ除去・音質調整・軽い部屋鳴り → 中村さんより少し小さく(-26LUFS)。"""
    au = s["audio"]
    out = work / f"satsuei_{au['start']:.2f}.wav"
    if not out.exists():
        src = p.dir / spec["satsuei_audio"]
        ad.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{au['start']:.3f}", "-to", f"{au['end']:.3f}", "-i", src,
                "-af", SATSUEI_CHAIN + ",loudnorm=I=-26:TP=-6:LRA=7,afade=t=in:d=0.02,areverse,afade=t=in:d=0.08,areverse",
                "-ac", "1", "-ar", "48000", out])
    return out, ad.ffprobe_duration(out)


def build_segments(p: ad.Project, spec: dict, work: Path, bg: dict) -> list[dict]:
    src = p.dir / spec["video"]
    green = spec.get("green", "0x78B23A")
    cache = p.edit / "talk_sdr"
    cache.mkdir(exist_ok=True)
    fw, fh = int(SW * FG_SCALE) // 2 * 2, int(SH * FG_SCALE) // 2 * 2
    fx, fy = (SW - fw) // 2, int(HEAD_Y * SH - SRC_HEAD_Y * fh)
    bg_file = p.dir / bg["file"]
    bg_size = tuple(int(v) for v in subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(bg_file)],
        capture_output=True, text=True).stdout.strip().split(","))
    durs = [frames(b - a) for a, b in (s["v"] for s in spec["segments"])]
    sdrs = [sdr_clip(src, s["v"][0], d, cache) for s, d in zip(spec["segments"], durs)]
    offs = align_offsets(sdrs, green) if spec.get("align", True) else [(0.0, 0.0)] * len(sdrs)
    ad.save_json(work / "align.json", [{"dy": round(a, 4), "dx": round(b, 4)} for a, b in offs])
    segs, t = [], 0.0
    for i, s in enumerate(spec["segments"]):
        dur, sdr = durs[i], sdrs[i]
        dy, dx = offs[i]
        ox = int(max(-(fw - SW) // 2 + 2, min((fw - SW) // 2 - 2, dx * fw)))
        oy = int(dy * fh)
        out = work / f"seg_{i:02d}.mp4"
        if not out.exists() or abs(ad.ffprobe_duration(out) - dur) > 0.05:
            fc = (bg_filter(bg, bg_size) +
                  f"[0:v]fps={FPS},scale={fw}:{fh},format=yuva444p,"
                  f"chromakey=color={green}:similarity=0.08:blend=0.04,"
                  f"despill=type=green:mix=0.6:expand=0.1,"
                  f"eq=brightness=0.05:contrast=1.04:saturation=1.04,colorbalance=rm=0.02:bm=-0.01[fg];"
                  f"[bg][fg]overlay={fx + ox}:{fy + oy}:shortest=1,format=yuv420p[v]")
            last = i == len(spec["segments"]) - 1
            fade = f"afade=t=in:d=0.03,afade=t=out:st={max(0, dur - (0.4 if last else 0.04)):.3f}:d={0.4 if last else 0.04}"
            if s["who"] == "satsuei" and s.get("audio"):  # 後撮りした撮影者の声を、少し間を空けて置く
                clip, _ = satsuei_clip(p, spec, s, work)
                lead = int(s["audio"].get("lead", 0.25) * 1000)
                amap = ["-i", clip]
                fc += f";[2:a]adelay={lead},apad=whole_dur={dur:.4f},aformat=channel_layouts=stereo[a]"
                aflt = ["-map", "[a]"]
            elif s["who"] == "satsuei":  # 撮影者の声は後で入れる → 無音の余白
                amap = ["-f", "lavfi", "-t", f"{dur:.4f}", "-i", "anullsrc=r=48000:cl=stereo"]
                aflt = ["-map", "2:a"]
            else:
                amap, aflt = [], ["-map", "0:a:0", "-af", fade]
            ad.run(["ffmpeg", "-y", "-v", "error", "-i", sdr, "-loop", "1", "-i", bg_file, *amap,
                    "-filter_complex", fc, "-map", "[v]", *aflt, "-t", f"{dur:.4f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-g", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out])
        segs.append({**s, "i": i, "at": round(t, 4), "len": dur, "file": out})
        t += dur
    return segs


def caption_parts(segs: list[dict], words: list[dict]) -> None:
    """'|' で区切ったテロップを、元動画の単語時刻（区間内）の文字位置に合わせて出す。撮影者区間は均等割り。"""
    for s in segs:
        a, b = s["v"]
        parts = s["telop"].split("|")
        if s["who"] == "nakamura":
            toks = [w for w in words if a - 0.05 <= w["start"] < b]
        else:
            toks = s.get("_words", [])  # 後撮りの撮影者の声があれば、その単語時刻に合わせる
        text, times = ad.char_times(toks) if toks else ("", [])
        keep = [k for k, c in enumerate(text) if c not in ad.PUNCT]
        tot = sum(len(ad.norm(plain(x))) for x in parts) or 1
        acc, out = 0, []
        for x in parts:
            frac = acc / tot
            if acc == 0:
                st = 0.0
            elif keep:
                st = times[keep[min(len(keep) - 1, int(frac * len(keep)))]] - a
            else:
                st = frac * s["len"]
            out.append({"text": x, "start": round(s["at"] + max(0.0, st), 3)})
            acc += len(ad.norm(plain(x)))
        for k, o in enumerate(out):
            o["end"] = out[k + 1]["start"] if k + 1 < len(out) else round(s["at"] + s["len"], 3)
        s["parts"] = out


def compose(p: ad.Project, segs: list[dict], total: float, base: Path, audio: Path,
            hf: Path | None = None, media_start: float = 0.0) -> None:
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

    els, js, caps = [], [], []
    for s in segs:
        sty, ls, le = s.get("style", "normal"), s["at"], round(s["at"] + s["len"], 3)
        if "punch" in s:  # パワーワードの瞬間だけ顔に向かってグッと寄り、区間の終わりで戻す
            pt = s["parts"][min(s["punch"], len(s["parts"]) - 1)]["start"]
            js.append(f'tl.fromTo("#base",{{scale:1}},{{scale:1.2,duration:0.3,ease:"power2.out"}},{pt:.3f});')
            js.append(f'tl.set("#base",{{scale:1}},{le:.3f});')
        if sty == "mono":
            js.append(f'tl.set("#base",{{filter:"grayscale(1) contrast(1.08)"}},{ls:.3f});')
            js.append(f'tl.set("#base",{{filter:"none"}},{le:.3f});')
        for k, part in enumerate(s["parts"]):
            st, du = part["start"], max(0.2, part["end"] - part["start"])
            eid = f"s{s['i']}_{k}"
            txt = part["text"]
            if sty in ("quote", "tate"):
                cols = txt.split("/")
                fs = int(min(104 if sty == "tate" else 78, 1180 / (max(len(plain(c)) for c in cols) + 0.5)))
                els.append(f'<div id="{eid}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                           f'data-track-index="2"><div class="{sty}" style="font-size:{fs}px">{markup(txt)}</div></div>')
                js.append(f'tl.fromTo("#{eid} .ln",{{opacity:0,y:-24}},{{opacity:1,y:0,duration:0.22,stagger:0.25}},{st:.3f});')
            else:
                base_fs = {"hook": 100, "red": 104, "mono": 96}.get(sty, 90)
                fs = fit(txt, base_fs, W - 120)
                lines = txt.split("/")
                cls = "cap" + (" stag" if len(lines) == 2 else "") + {"yellow": " yel", "red": " red", "mono": " mono"}.get(sty, "")
                els.append(f'<div id="{eid}" class="clip layer" data-start="{st:.3f}" data-duration="{du:.3f}" '
                           f'data-track-index="2"><div class="{cls}"><div class="blk" style="font-size:{fs}px">'
                           f'{markup(txt)}</div></div></div>')
                if sty in ("red", "hook") and k == len(s["parts"]) - 1:
                    js.append(f'tl.fromTo("#{eid} .blk",{{scale:0.8,opacity:0}},{{scale:1,opacity:1,duration:0.16,'
                              f'ease:"back.out(2)"}},{st:.3f});')
            caps.append({"start": st, "end": round(st + du, 3), "hook": sty == "hook",
                         "who": s["who"], "text": plain(txt.replace("/", "\n"))})
        if s.get("disclaimer"):
            els.append(f'<div id="d{s["i"]}" class="clip layer" data-start="{ls:.3f}" data-duration="{le - ls:.3f}" '
                       f'data-track-index="5"><div class="disc">{escape(s["disclaimer"])}</div></div>')
        if sty == "cta":
            els.append(f'<div id="c{s["i"]}" class="clip layer" data-start="{ls:.3f}" data-duration="{le - ls:.3f}" '
                       f'data-track-index="4"><div class="ctabox">{markup(s["cta"])}</div>'
                       f'<div class="arrows"><span>↓</span><span>↓</span><span>↓</span></div></div>')
            js.append(f'tl.fromTo("#c{s["i"]} .ctabox",{{scale:0.85,opacity:0}},{{scale:1,opacity:1,duration:0.18}},{ls:.3f});')
            js.append(f'tl.fromTo("#c{s["i"]} .arrows span",{{y:0}},{{y:14,duration:0.28,yoyo:true,'
                      f'repeat:{max(1, int((le - ls) / 0.56))},stagger:0.07,ease:"sine.inOut"}},{ls + 0.15:.3f});')
        if sty == "card":
            sub, title = (s["card"].split("/") + [""])[:2]
            els.append(f'<div id="k{s["i"]}" class="clip layer" data-start="{ls:.3f}" data-duration="{le - ls:.3f}" '
                       f'data-track-index="4"><div class="card"><div class="sub">{escape(sub)}</div>'
                       f'<div class="ttl">{escape(title)}</div></div></div>')
            js.append(f'tl.fromTo("#k{s["i"]} .card",{{scale:0.4,opacity:0,rotation:-12}},{{scale:1,opacity:1,rotation:-3,'
                      f'duration:0.35,ease:"back.out(2.2)"}},{ls:.3f});')

    html = f"""<!doctype html>
<html lang="ja" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<script src="vendor/gsap.min.js"></script>
<style>
@font-face {{ font-family: "Noto"; src: url("fonts/noto.ttf") format("truetype"); font-weight: 100 900; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; font-family: "Noto", sans-serif; }}
#base {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; transform-origin: 50% 24%; }}
.layer {{ position: absolute; inset: 0; pointer-events: none; }}
.cap {{ position: absolute; left: 60px; right: 60px; top: 1020px; display: flex; justify-content: center; }}
.blk {{ display: inline-flex; flex-direction: column; align-items: center; color: #fff; font-weight: 900;
  transform: skewX(-8deg);
  line-height: 1.22; letter-spacing: -0.01em; -webkit-text-stroke: 2px rgba(20,20,20,.55);
  text-shadow: 0 0 3px rgba(0,0,0,.95), 0 0 10px rgba(0,0,0,.55), 0 5px 12px rgba(0,0,0,.55); }}
.stag .blk .ln:first-child {{ align-self: flex-start; }}
.stag .blk .ln:last-child {{ align-self: flex-end; }}
.ln {{ white-space: nowrap; }}
.y, .yel .blk {{ color: #FFE600; }}
.big {{ display: inline-block; color: #FFE600; font-size: 1.45em; transform: skewX(-6deg); line-height: 1; }}
.r, .red .blk {{ color: #FF2B2B; }}
.mono .blk {{ color: #A95CFF; }}
.quote {{ position: absolute; right: 80px; top: 300px; writing-mode: vertical-rl; color: #fff; font-weight: 900;
  line-height: 1.12; text-shadow: 0 2px 6px rgba(0,0,0,.6); }}
.quote .ln {{ background: rgba(176,140,40,.92); padding: 14px 6px; margin-left: 10px; }}
.tate {{ position: absolute; right: 70px; top: 280px; writing-mode: vertical-rl; color: #FFE600; font-weight: 900;
  line-height: 1.08; -webkit-text-stroke: 2px rgba(20,20,20,.5);
  text-shadow: 0 0 3px rgba(0,0,0,.95), 0 0 12px rgba(0,0,0,.55), 0 5px 12px rgba(0,0,0,.5); }}
.tate .ln {{ margin-left: 6px; }}
.ctabox {{ position: absolute; left: 130px; right: 130px; top: 1260px; background: #E8383D; color: #fff;
  font-weight: 900; font-size: 50px; text-align: center; line-height: 1.3; padding: 22px 16px; border-radius: 26px;
  box-shadow: 0 8px 22px rgba(0,0,0,.3); }}
.arrows {{ position: absolute; left: 0; right: 0; top: 1440px; display: flex; justify-content: center; gap: 90px;
  color: #FFE600; font-size: 96px; font-weight: 900; text-shadow: 0 0 4px rgba(0,0,0,.9), 0 4px 10px rgba(0,0,0,.5); }}
.arrows span {{ display: inline-block; }}
.card {{ position: absolute; left: 110px; top: 1300px; width: 860px; background: #fff; border-radius: 14px;
  border-top: 22px solid #F28C28; padding: 26px 28px; box-shadow: 0 14px 30px rgba(0,0,0,.35); }}
.card .sub {{ font-size: 40px; font-weight: 800; color: #444; }}
.card .ttl {{ font-size: 104px; font-weight: 900; color: #F28C28; line-height: 1.15; margin-top: 6px; white-space: nowrap; }}
.disc {{ position: absolute; left: 0; right: 0; top: 1300px; text-align: center; color: #fff; font-size: 26px;
  font-weight: 600; text-shadow: 0 1px 4px rgba(0,0,0,.95); }}
</style>
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
    if hf == p.hf:  # 分割書き出し用のパートでは上書きしない（テロップ一覧は全体版だけ）
        ad.save_json(p.edit / "captions.json", caps)


def split_parts(segs: list[dict], max_len: float = 20.0) -> list[list[dict]]:
    """書き出しを分割する単位：カットの境目で、1パート max_len 秒以下に分ける。"""
    parts, cur, cur_len = [], [], 0.0
    for s in segs:
        if cur and cur_len + s["len"] > max_len:
            parts.append(cur)
            cur, cur_len = [], 0.0
        cur.append(s)
        cur_len += s["len"]
    if cur:
        parts.append(cur)
    return parts


def shifted(seg: dict, t0: float) -> dict:
    out = {**seg, "at": round(seg["at"] - t0, 4)}
    out["parts"] = [{**x, "start": round(x["start"] - t0, 3), "end": round(x["end"] - t0, 3)} for x in seg["parts"]]
    return out


def render_parts(p: ad.Project, segs: list[dict], total: float, base: Path, audio: Path, work: Path,
                 draft: bool) -> Path:
    """8GB 環境ではおよそ1500フレームを超えると書き出しが止まるため、約20秒ずつ書き出してつなぐ。
    音声はつなぎ目でプツッとしないよう、最後に元の音声トラックをまるごと載せ直す。"""
    env = {**os.environ, "PRODUCER_BROWSER_GPU_MODE": os.environ.get("PRODUCER_BROWSER_GPU_MODE", "hardware")}
    outs = []
    for k, chunk in enumerate(split_parts(segs)):
        t0 = chunk[0]["at"]
        dur = round(sum(x["len"] for x in chunk), 4)
        hf = work / f"hf_part{k}"
        compose(p, [shifted(x, t0) for x in chunk], dur, base, audio, hf=hf, media_start=t0)
        out = work / f"part{k}.mp4"
        for attempt in range(4):
            r = subprocess.run([str(c) for c in [ad.HF_BIN, "render", hf, "-o", out, "--fps", FPS,
                                                  "-q", "draft" if draft else "delivery"]], env=env)
            if r.returncode == 0:
                break
            subprocess.run(["pkill", "-f", "chrome-headless-shell"])
            ad.log(f"パート{k + 1}の書き出しが止まったのでやり直します")
        else:
            sys.exit(f"パート{k + 1}の書き出しに失敗しました")
        ad.log(f"パート{k + 1} 完了（{t0:.1f}〜{t0 + dur:.1f}秒）")
        outs.append(out)
    (work / "parts.txt").write_text("".join(f"file '{o.name}'\n" for o in outs))
    raw = work / "render_raw.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", work / "parts.txt", "-i", audio,
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", raw])
    return raw


def cmd_talk(a) -> None:
    p = ad.Project(a.name)
    spec = ad.load_json(p.dir / "edit.json")
    bgs = spec.get("backgrounds") or {"main": {"file": spec["background"]}}
    keys = list(bgs) if a.bg == "all" else [a.bg or next(iter(bgs))]
    for key in keys:
        render_one(a, p, spec, key, bgs[key])


def render_one(a, p: ad.Project, spec: dict, key: str, bg: dict) -> None:
    ad.log(f"背景 {key}: {bg['file']}")
    work = p.edit / f"talk_{key}"
    work.mkdir(parents=True, exist_ok=True)
    words_path = p.edit / "video_words_norm.json"
    if not words_path.exists():
        ad.save_json(words_path, ad.transcribe_whisper(p.dir / spec["video"], p.edit / "video_words.json"))
    words = ad.load_json(words_path)
    segs = build_segments(p, spec, work, bg)
    total = round(sum(s["len"] for s in segs), 4)
    n_sat = sum(1 for s in segs if s["who"] == "satsuei")
    ad.log(f"{len(segs)} 区間・{total:.1f} 秒（うち撮影者の余白 {n_sat} 区間・"
           f"{sum(s['len'] for s in segs if s['who'] == 'satsuei'):.1f} 秒）")
    (work / "list.txt").write_text("".join(f"file '{s['file'].name}'\n" for s in segs))
    joined = work / "joined.mp4"
    ad.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", work / "list.txt", "-c", "copy", joined])
    base = work / "base.mp4"
    # 8GB 環境の書き出し安定のため、ベース映像は 1080×1920・30fps・標準色域に（ズーム時は少しだけ甘くなる）
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", joined, "-vf",
            f"fps={FPS},scale={W}:{H}:flags=lanczos:in_range=full:out_range=tv,format=yuv420p,"
            "tpad=stop_mode=clone:stop_duration=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-g", str(FPS), "-keyint_min", str(FPS),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", base])
    audio = work / "voice.m4a"
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", joined, "-vn", "-c:a", "aac", "-b:a", "192k", audio])
    for s in segs:  # 撮影者の声の単語時刻（区間の元動画の時刻に換算）
        if s["who"] == "satsuei" and s.get("audio"):
            clip, _ = satsuei_clip(p, spec, s, work)
            wj = clip.with_suffix(".words.json")
            ws = ad.load_json(wj) if wj.exists() else ad.transcribe_whisper(clip, clip.with_suffix(".whisper.json"))
            ad.save_json(wj, ws)
            off = s["v"][0] + s["audio"].get("lead", 0.25)
            s["_words"] = [{**w, "start": w["start"] + off, "end": w["end"] + off} for w in ws]
    caption_parts(segs, words)
    ad.save_json(work / "timeline.json", [{k: (str(v) if isinstance(v, Path) else v) for k, v in s.items()} for s in segs])
    compose(p, segs, total, base, audio)  # 全体版（プレビュー・テロップ一覧用）
    lint = subprocess.run([ad.HF_BIN, "lint", str(p.hf)], capture_output=True, text=True)
    print((lint.stdout or lint.stderr).strip().splitlines()[-1])
    raw = render_parts(p, segs, total, base, audio, work, a.draft)
    final = ad.loudnorm_to_output(p, raw, suffix=f"_{key}" + ("_draft" if a.draft else ""))
    p.set_state(rendered=str(final))
    ad.log(f"→ {final.relative_to(ad.STUDIO)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--bg", default="all")
    cmd_talk(ap.parse_args())
