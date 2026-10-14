#!/usr/bin/env python3
"""ugc.py で作った動画（1.25倍速後）に、控えめな効果音を重ねる。BGM を入れる前の動画に使う。

  python3 tools/sfx_mix.py <project> <動画ファイル名(output/内)> --variant 冒頭1 --speed 1.25 --suffix _sfx

入れる場所（控えめ）：
- 冒頭：大きい数字（#語#）にキラッ、赤字（!語!）にドン（小さめ）
- 経歴の画像（訪問販売／飲食副店長／買取）の切り替えに、小さなポン
- 「でもそこでAIに出会った」にシュッ＋キラッ（転機）
- 「2ヶ月で」（本編）にキラッ
- 上下分割のズーム場面の頭にシュッ
- 「ほぼ実践型」にキラッ
- LINE のアイコンが出る所／「無料の副業相談」／「副業ガイドブック」にポン
マイナスの話（現場の仕事・落ちまくりました）と、最後の一言には入れない。
テロップの出る時刻は edit/ugc_<variant>/timeline.json の parts（1.25倍速前の秒）を speed で割って使う。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ad  # noqa: E402

FILES = {"pop": "pa1.mp3", "kira": "kira2.mp3", "whoosh": "highspeed-movement1.mp3", "don": "don-1.mp3",
         "ng": "candidates/incorrect1.mp3", "stab": "candidates/knife-stab-3.mp3",
         "popi": "candidates/decision35.mp3", "gaan": "candidates/shock2.mp3"}
VOL = {"pop": 0.30, "kira": 0.30, "whoosh": 0.30, "don": 0.34, "ng": 0.32, "stab": 0.32, "popi": 0.34, "gaan": 0.55}     # 控えめ
TRIM = {"kira": 1.2, "don": 1.1, "stab": 1.0, "gaan": 1.7}


def events(segs: list[dict], speed: float) -> list[tuple[str, float]]:
    ev: list[tuple[str, float]] = []
    first_stack = True
    for s in segs:
        for nm, at in s.get("sfx_list") or []:  # 区間の頭からの秒で、効果音を直接指定（この区間の自動ルールは使わない）
            ev.append((nm, (s["at"] + at) / speed))
        for k, part in enumerate(s.get("parts", [])):
            t, txt = part["start"] / speed, part["text"]
            src = s["src"]
            if s.get("sfx_list") or any(it.get("kind") != "qbox" or it.get("hide_telop") for it in (s.get("ftele") or [])):
                pass
            elif src in ("ashimoto", "food1", "food2", "hookgs") or s.get("hook_sfx"):  # 冒頭
                if txt.startswith("ただ"):
                    ev.append(("don", t))
                elif "#" in txt:
                    ev.append(("kira", t))
                elif "!" in txt:
                    ev.append(("don", t))
            elif src in ("img_houmon", "img_inshoku", "img_kaitori"):
                ev.append(("pop", t))
            if "でもそこで" in txt:
                ev += [("whoosh", max(0.0, t - 0.12)), ("kira", t)]
            elif txt.startswith("#2ヶ月#") and src != "ashimoto":
                ev.append(("kira", t))
            if src == "pre_stack_zoom" and first_stack and k == 0:
                ev.append(("whoosh", max(0.0, t - 0.1)))
                first_stack = False
            if "#ほぼ実践型#" in txt:
                ev.append(("kira", t))
            if "*無料の副業相談*" in txt or "*副業ガイドブック*" in txt:
                ev.append(("pop", t))
        for it in s.get("ftele") or []:  # 参考風テロップ：sfx を指定したものだけ
            if it.get("sfx"):
                ev.append((it["sfx"], (s["at"] + it.get("at", 0.0)) / speed))
            for nm, at in it.get("sfx_extra") or []:
                ev.append((nm, (s["at"] + at) / speed))
            if it.get("sfx_out"):
                ev.append((it["sfx_out"], (s["at"] + it["to"]) / speed))
        for o in s.get("overlays") or []:  # 図解の重ね：sfx を指定したものだけ
            part = s["parts"][o["part"]]
            d = part["end"] - part["start"]
            for it in o["items"]:
                if it.get("sfx"):
                    ev.append((it["sfx"], (part["start"] + (o.get("from", 0.0) + it.get("at", 0.0) * (o.get("to", 1.0) - o.get("from", 0.0))) * d) / speed))
        if s.get("logo"):
            ev.append(("pop", s["at"] / speed + 0.1))
    return sorted(ev, key=lambda e: e[1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("video")
    ap.add_argument("--variant", required=True)
    ap.add_argument("--speed", type=float, default=1.25)
    ap.add_argument("--suffix", default="_sfx")
    a = ap.parse_args()
    p = ad.Project(a.project)
    video = p.output / a.video
    segs = json.loads((p.edit / f"ugc_{a.variant}" / "timeline.json").read_text(encoding="utf-8"))
    ev = events(segs, a.speed)
    ins, fc, labels = [], "", ["[0:a]"]
    for n, (name, t) in enumerate(ev):
        ins += ["-i", ad.STUDIO / "sfx" / FILES[name]]
        tail = f",atrim=0:{TRIM[name]},afade=t=out:st={TRIM[name] - 0.3}:d=0.3" if name in TRIM else ""
        fc += (f"[{n + 1}:a]aresample=48000,aformat=channel_layouts=stereo,volume={VOL[name]}{tail},"
               f"adelay={int(t * 1000)}:all=1[e{n}];")
        labels.append(f"[e{n}]")
    fc += "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first[a]"
    out = p.output / (Path(a.video).stem + a.suffix + ".mp4")
    ad.run(["ffmpeg", "-y", "-v", "error", "-i", video, *ins, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out])
    ad.log(f"効果音 {len(ev)} か所 → {out.relative_to(ad.STUDIO)}")
    for name, t in ev:
        print(f"  {t:5.1f}s  {name}")


if __name__ == "__main__":
    main()
