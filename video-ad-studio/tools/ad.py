#!/usr/bin/env python3
"""縦型動画広告の自動編集パイプライン。

  ad new <name> [--from FILE ...]   プロジェクト作成（素材を input/ へ）
  ad transcribe <name>              文字起こし（Scribe → なければローカル Whisper）
  ad plan <name>                    無音・フィラー・言い直しのカット案を作る
  ad approve <name>                 カット案を承認（edit/edl.json を手で直してからでもよい）
  ad cut <name>                     承認済みカットを 1080x1920 に書き出し
  ad compose <name>                 HyperFrames でテロップ・SE・ズーム・CTA を組む
  ad render <name> [--draft]        レンダリング → ラウドネス調整 → output/
  ad qa <name>                      書き出し後の自己チェック（output/qa_report.md）
  ad all <name> [--yes]             上をまとめて実行（未承認ならカット案で止まる）

素材の置き場: projects/<name>/input/   設定: brand/brand.json, projects/<name>/brief.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import date
from html import escape
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent
PROJECTS = STUDIO / "projects"
VIDEO_USE = Path(os.environ.get("VIDEO_USE_DIR", Path.home() / "Developer/video-use"))
HF_BIN = STUDIO / "node_modules/.bin/hyperframes"
WHISPER_MODEL = Path(os.environ.get(
    "WHISPER_MODEL", Path.home() / ".cache/hyperframes/whisper/models/ggml-large-v3.bin"))
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}
W, H, FPS = 1080, 1920, 30
SENT_END = "。？！?!"
PUNCT = "。、，,．.？！?!「」『』（）()・…〜~ 　"

sys.path.insert(0, str(VIDEO_USE / "helpers"))
try:  # video-use の HDR 判定を再利用（iPhone の HLG 素材対策）
    from render import TONEMAP_CHAIN, is_hdr_source  # type: ignore
except Exception:  # pragma: no cover
    TONEMAP_CHAIN, is_hdr_source = None, (lambda p: False)


# ----------------------------------------------------------------- utilities
def log(msg: str) -> None:
    print(f"▶ {msg}", flush=True)


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def load_json(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def brand() -> dict:
    return load_json(STUDIO / "brand/brand.json")


class Project:
    def __init__(self, name: str):
        self.name = name
        self.dir = PROJECTS / name
        if not self.dir.exists():
            sys.exit(f"プロジェクトがありません: {self.dir}（ad new {name} で作成）")
        self.input = self.dir / "input"
        self.edit = self.dir / "edit"
        self.output = self.dir / "output"
        self.hf = self.edit / "hf"
        self.brief = load_json(self.dir / "brief.json", {})
        self.state_path = self.edit / "state.json"

    @property
    def state(self) -> dict:
        return load_json(self.state_path, {})

    def set_state(self, **kw) -> None:
        s = self.state
        s.update(kw)
        save_json(self.state_path, s)

    def sources(self) -> list[Path]:
        vids = sorted(p for p in self.input.iterdir() if p.suffix.lower() in VIDEO_EXT)
        if not vids:
            sys.exit(f"素材がありません: {self.input} に動画を入れてください")
        return vids


def ffprobe_duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return "".join(c for c in s if c not in PUNCT and not c.isspace())


# ------------------------------------------------------------------ new
def cmd_new(a) -> None:
    d = PROJECTS / a.name
    for sub in ("input", "broll", "edit", "output"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    if not (d / "brief.json").exists():
        brief = load_json(STUDIO / "templates/brief.json")
        brief["title"] = a.name
        save_json(d / "brief.json", brief)
    for f in a.from_files or []:
        src = Path(f).expanduser()
        dst = d / "input" / src.name
        (shutil.move if a.move else shutil.copy2)(src, dst)
        log(f"素材を追加: {dst.relative_to(STUDIO)}")
    log(f"作成しました: {d.relative_to(STUDIO)}（brief.json に目的・CTA・尺を書く）")


# ------------------------------------------------------------ transcribe
def scribe_key_available() -> bool:
    if os.environ.get("ELEVENLABS_API_KEY"):
        return True
    env = VIDEO_USE / ".env"
    return env.exists() and re.search(r"^ELEVENLABS_API_KEY=.+", env.read_text(), re.M) is not None


def whisper_prompt() -> str:
    b = brand()
    terms = [b["name"], *sorted(set(b["glossary"].values())), "査定", "買取"]
    return "、".join(terms) + "。"


def whisper_dtw_preset() -> str:
    # ggml-large-v3.bin → large.v3（whisper-cli の DTW 用プリセット名）
    return WHISPER_MODEL.stem.removeprefix("ggml-").split("-q")[0].replace("-", ".")


def transcribe_whisper(video: Path, out_json: Path) -> list[dict]:
    if not WHISPER_MODEL.exists():
        sys.exit(f"Whisper モデルがありません: {WHISPER_MODEL}\n  bash tools/setup.sh を実行してください")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    stem = out_json.parent / out_json.name.removesuffix(".json")  # whisper-cli は -of に .json を付ける
    wav = out_json.parent / (out_json.name + ".wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
    run(["whisper-cli", "-m", WHISPER_MODEL, "-f", wav, "-l", "ja", "-ojf", "-of", stem,
         "--prompt", whisper_prompt(), "-t", "8", "-dtw", whisper_dtw_preset(), "-nfa"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wav.unlink(missing_ok=True)
    raw = json.loads(out_json.read_bytes().decode("utf-8", "surrogateescape"))
    # DTW の時刻（センチ秒）を各トークンの開始時刻として使う。終了は次トークン開始まで
    toks: list[dict] = []
    pending, p_t = b"", None
    for seg in raw["transcription"]:
        seg_end = seg["offsets"]["to"] / 1000
        for t in seg["tokens"]:
            txt = t["text"]
            if txt.startswith("[_") or txt.startswith("<|"):
                continue
            ts = t["t_dtw"] / 100 if t.get("t_dtw", -1) >= 0 else t["offsets"]["from"] / 1000
            b = pending + txt.encode("utf-8", "surrogateescape")
            try:
                s = b.decode("utf-8")
            except UnicodeDecodeError:  # 文字の途中で切れたトークンは次とつなぐ
                pending, p_t = b, ts if p_t is None else p_t
                continue
            ts = ts if p_t is None else p_t
            pending, p_t = b"", None
            if s.strip():
                toks.append({"text": s.strip(), "start": ts, "seg_end": seg_end})
    words = []
    for i, t in enumerate(toks):
        nxt = toks[i + 1]["start"] if i + 1 < len(toks) else t["seg_end"]
        punct = all(c in PUNCT for c in t["text"])
        est = 0.0 if punct else max(0.15, 0.13 * len(t["text"]))
        end = min(max(nxt, t["start"]), t["start"] + est)
        if i + 1 == len(toks) or toks[i + 1]["seg_end"] != t["seg_end"]:
            end = max(end, min(t["seg_end"], t["start"] + est + 0.2)) if not punct else end
        words.append({"text": t["text"], "start": round(t["start"], 3), "end": round(end, 3)})
    return words


def transcribe_scribe(video: Path, edit: Path) -> list[dict]:
    run(["uv", "run", "--project", VIDEO_USE, "python", VIDEO_USE / "helpers/transcribe.py",
         video, "--edit-dir", edit, "--language", "ja"])
    raw = load_json(edit / "transcripts" / f"{video.stem}.json")
    words = []
    for w in raw.get("words", []):
        if w.get("type") == "spacing" or not w.get("text", "").strip():
            continue
        words.append({"text": w["text"].strip(), "start": w["start"], "end": w["end"],
                      **({"type": "event"} if w.get("type") == "audio_event" else {})})
    return words


def cmd_transcribe(a) -> None:
    p = Project(a.name)
    engine = a.engine or p.brief.get("transcribe_engine", "auto")
    if engine == "auto":
        engine = "scribe" if scribe_key_available() else "whisper"
    for v in p.sources():
        out = p.edit / "words" / f"{v.stem}.json"
        if out.exists() and not a.force:
            log(f"キャッシュ済み: {v.name}")
            continue
        log(f"文字起こし（{engine}）: {v.name}")
        words = transcribe_scribe(v, p.edit) if engine == "scribe" else \
            transcribe_whisper(v, p.edit / "transcripts" / f"{v.stem}.whisper.json")
        save_json(out, {"source": str(v), "engine": engine, "words": words})
        log(f"  {len(words)} トークン → {out.relative_to(p.dir)}")
    p.set_state(transcribed=True, engine=engine)


# ------------------------------------------------------------------ plan
def phrases_from_words(words: list[dict], min_gap: float, clauses: bool = False,
                       strict: bool = False) -> list[list[dict]]:
    """無音・文末で区切る。clauses=True なら読点でも区切る（言い直し検出用）。
    strict=True（Whisper）では時刻が粗いので、句読点の位置か 0.6 秒以上の無音でだけ区切る。"""
    out, cur = [], []
    for w in words:
        if w.get("type") == "event":
            continue
        if cur and not all(c in PUNCT for c in w["text"]):  # 句読点は直前の発話にくっつける
            gap = w["start"] - cur[-1]["end"]
            last = cur[-1]["text"][-1]
            at_punct = last in SENT_END or last in "、,"
            split = last in SENT_END or (clauses and last in "、,")
            split = split or (gap >= min_gap and (not strict or at_punct or gap >= 0.6))
            if split:
                out.append(cur)
                cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def strip_leading_fillers(ph: list[dict], fillers: list[str]) -> tuple[list[dict], str]:
    """先頭の「えーと、」などを落とす。落としたフィラー文字列を返す。"""
    removed = ""
    fl = sorted(fillers, key=len, reverse=True)
    while ph:
        text = "".join(w["text"] for w in ph)
        hit = next((f for f in fl if re.match(rf"{re.escape(f)}[ー〜ぅう]*[、,。\s]", text)
                    or norm(text) == f), None)
        if not hit:
            break
        m = re.match(rf"{re.escape(hit)}[ー〜ぅう]*[、,。\s]?", text)
        n, acc = len(m.group(0)), 0
        k = 0
        while k < len(ph) and acc < n:
            acc += len(ph[k]["text"])
            k += 1
        removed += text[:acc]
        ph = ph[k:]
    return ph, removed


def audio_envelope(src: Path) -> tuple[list[float], float]:
    """10ms ごとの音量（dBFS）と、発話とみなすしきい値を返す。"""
    import array
    import math
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = array.array("h", raw)
    env = []
    for i in range(0, len(a), 160):
        blk = a[i:i + 160]
        rms = math.sqrt(sum(x * x for x in blk) / max(len(blk), 1)) or 1e-9
        env.append(20 * math.log10(rms / 32768))
    loud = sorted(env)[int(len(env) * 0.95)] if env else -20
    return env, max(loud - 32, -55.0)


def snap_to_audio(env: list[float], thr: float, start: float, end: float) -> tuple[float, float]:
    """単語タイムスタンプのズレを吸収：実際の音の立ち上がり/減衰までカット点を広げる（最大 0.3 秒）。"""
    i = int(start * 100)
    for _ in range(30):
        if i <= 0 or max(env[max(0, i - 3):i]) < thr:  # 30ms 静かなら、そこが発話の頭
            break
        i -= 1
    j = int(end * 100)
    for _ in range(30):
        if j >= len(env) - 3 or max(env[j:j + 3]) < thr:
            break
        j += 1
    return max(0.0, i / 100 - 0.03), min(len(env) / 100, j / 100 + 0.05)


def cmd_plan(a) -> None:
    p = Project(a.name)
    brief_min_gap = p.brief.get("min_silence", 0.25)
    br = brand()
    sources, items = {}, []
    for wf in sorted((p.edit / "words").glob("*.json")):
        data = load_json(wf)
        src = Path(data["source"])
        sid = src.stem
        sources[sid] = str(src)
        dur = ffprobe_duration(src)
        phs = phrases_from_words(data["words"], brief_min_gap, clauses=True,
                                 strict=data.get("engine") == "whisper")
        for i, ph in enumerate(phs):
            kept, filler = strip_leading_fillers(ph, br["fillers"])
            text = "".join(w["text"] for w in ph)
            it = {"source": sid, "idx": i, "text": text, "start": ph[0]["start"], "end": ph[-1]["end"],
                  "keep": True, "reason": "", "dur": dur}
            if not kept:
                it.update(keep=False, reason="フィラーのみ")
            elif filler:
                it.update(start=kept[0]["start"], reason=f"先頭フィラー「{filler.strip()}」を削除",
                          text=text)
            items.append(it)
    # 言い直し検出：直後 2 フレーズ以内に同じ言い出しがあれば前を落とす
    for i, it in enumerate(items):
        if not it["keep"]:
            continue
        a_n = norm(it["text"])
        for j in range(i + 1, min(i + 3, len(items))):
            nx = items[j]
            if nx["source"] != it["source"] or not nx["keep"]:
                continue
            b_n = norm(nx["text"])
            head = a_n[: max(3, len(a_n) // 2)]
            ratio = difflib.SequenceMatcher(None, a_n, b_n[: len(a_n) + 2]).ratio()
            if len(a_n) >= 3 and (b_n.startswith(head) or ratio >= 0.75) and len(b_n) >= len(a_n) * 0.8:
                it.update(keep=False, reason=f"言い直し候補（→「{nx['text'][:14]}…」を採用）")
                break
    # パディング付きレンジ化（30–200ms の範囲）→ 実音声にスナップ → 隣と重ならないよう調整
    pre, post = 0.05, 0.08
    envs = {sid: audio_envelope(Path(path)) for sid, path in sources.items()}
    ranges = []
    for it in items:
        if not it["keep"]:
            continue
        env, thr = envs[it["source"]]
        s, e = snap_to_audio(env, thr, max(0.0, it["start"] - pre), min(it["dur"], it["end"] + post))
        if ranges and ranges[-1]["source"] == it["source"] and s - ranges[-1]["end"] < 0.12:
            ranges[-1]["end"] = round(max(e, ranges[-1]["end"]), 3)
            ranges[-1]["quote"] += it["text"]
            continue
        if ranges and ranges[-1]["source"] == it["source"] and s < ranges[-1]["end"]:
            s = ranges[-1]["end"]
        ranges.append({"source": it["source"], "start": round(s, 3), "end": round(e, 3),
                       "quote": it["text"], "reason": it["reason"] or "発話"})
    total = sum(r["end"] - r["start"] for r in ranges)
    edl = {"version": 1, "sources": sources, "ranges": ranges, "total_duration_s": round(total, 2)}
    save_json(p.edit / "edl.json", edl)

    target = p.brief.get("target_seconds", 15)
    lines = [f"# カット案: {p.name}", "",
             f"- 推定尺: **{total:.1f} 秒**（目標 {target} 秒）"
             + ("  ⚠️ 目標超過。下の ✅ から削る行を選んでください" if total > target * 1.1 else ""),
             f"- 無音しきい値: {brief_min_gap}s / パディング 前{int(pre*1000)}ms・後{int(post*1000)}ms（＋波形で発話の頭・お尻にスナップ）",
             "", "| | 時間 | 発話 | 判定理由 |", "|---|---|---|---|"]
    for it in items:
        mark = "✅" if it["keep"] else "✂️"
        lines.append(f"| {mark} | {it['source']} {it['start']:.2f}–{it['end']:.2f} | {it['text']} | {it['reason']} |")
    lines += ["", "## 承認方法",
              "- このままで良ければ: `ad approve " + p.name + "`",
              "- 直したい場合: `edit/edl.json` の ranges を編集（または AI に「◯◯の行も削って」と指示）してから approve",
              "- 言い直し判定は機械的な候補です。意味的に残すべきものは AI/人が判断してください"]
    (p.edit / "cut_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    p.set_state(planned=True, approved=False)
    print("\n".join(lines))


def cmd_approve(a) -> None:
    p = Project(a.name)
    if not (p.edit / "edl.json").exists():
        sys.exit("先に ad plan を実行してください")
    p.set_state(approved=True, approved_on=str(date.today()))
    log("カット案を承認しました")


# ------------------------------------------------------------------- cut
def cmd_cut(a) -> None:
    p = Project(a.name)
    if not p.state.get("approved") and not a.force:
        sys.exit("カット案が未承認です。edit/cut_plan.md を確認して `ad approve` してください")
    edl = load_json(p.edit / "edl.json")
    seg_dir = p.edit / "segments"
    shutil.rmtree(seg_dir, ignore_errors=True)
    seg_dir.mkdir(parents=True)
    segs, offset, timeline = [], 0.0, []
    words_by_src = {Path(load_json(f)["source"]).stem: load_json(f)["words"]
                    for f in (p.edit / "words").glob("*.json")}
    for i, r in enumerate(edl["ranges"]):
        src = Path(edl["sources"][r["source"]])
        d = r["end"] - r["start"]
        vf = []
        if TONEMAP_CHAIN and is_hdr_source(src):
            vf.append(TONEMAP_CHAIN)
        vf.append(f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}")
        af = f"afade=t=in:st=0:d=0.03,afade=t=out:st={max(0, d - 0.03):.3f}:d=0.03"
        out = seg_dir / f"seg_{i:03d}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{r['start']:.3f}", "-i", src, "-t", f"{d:.3f}",
             "-vf", ",".join(vf), "-af", af, "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", out])
        real = ffprobe_duration(out)
        for w in words_by_src.get(r["source"], []):
            if w.get("type") == "event" or w["end"] <= r["start"] or w["start"] >= r["end"]:
                continue
            timeline.append({"text": w["text"],
                             "start": round(max(0, w["start"] - r["start"]) + offset, 3),
                             "end": round(min(d, w["end"] - r["start"]) + offset, 3)})
        segs.append(out)
        offset += real
    lst = seg_dir / "list.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segs))
    cut = p.edit / "cut.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
         "-movflags", "+faststart", cut])
    save_json(p.edit / "timeline_words.json", timeline)
    p.set_state(cut=True, cut_duration=round(ffprobe_duration(cut), 3))
    log(f"カット書き出し: {cut.relative_to(p.dir)}（{ffprobe_duration(cut):.2f}s）")


# --------------------------------------------------------------- captions
def char_times(phrase: list[dict]) -> tuple[str, list[float]]:
    text, times = "", []
    for w in phrase:
        n = len(w["text"])
        for k in range(n):
            times.append(w["start"] + (w["end"] - w["start"]) * k / max(n, 1))
        text += w["text"]
    return text, times


def apply_glossary(text: str, times: list[float], glossary: dict) -> tuple[str, list[float]]:
    if not glossary:
        return text, times
    pat = re.compile("|".join(re.escape(k) for k in sorted(glossary, key=len, reverse=True)))
    out, ot, pos = "", [], 0
    for m in pat.finditer(text):
        out += text[pos:m.start()]
        ot += times[pos:m.start()]
        rep = glossary[m.group(0)]
        out += rep
        ot += [times[m.start()]] * len(rep)
        pos = m.end()
    return out + text[pos:], ot + times[pos:]


def highlight_mask(text: str, terms: list[str]) -> list[str]:
    """各文字に '' / 'hl' / 'price' を付ける。"""
    mask = [""] * len(text)
    num = r"[0-9０-９][0-9０-９,，.．]*\s*(万|千|億)?\s*(円|%|％|割|倍|点|年|日|分|秒|時間|件)?|[一二三四五六七八九十百千万]+(万|千)?円"
    for m in re.finditer(num, text):
        kind = "price" if "円" in m.group(0) else "hl"
        for i in range(m.start(), m.end()):
            mask[i] = kind
    for t in terms:
        for m in re.finditer(re.escape(t), text):
            for i in range(m.start(), m.end()):
                mask[i] = mask[i] or "hl"
    return mask


def build_captions(words: list[dict], br: dict, brief: dict, total: float, strict: bool = False) -> list[dict]:
    import budoux
    parser = budoux.load_default_japanese_parser()
    cfg = br["caption"]
    caps = []
    for pi, ph in enumerate(phrases_from_words(words, 0.3, strict=strict)):
        text, times = char_times(ph)
        text, times = apply_glossary(text, times, br["glossary"])
        text = text.replace("?", "？").replace("!", "！")
        hook = pi == 0 and brief.get("hook_style_first_caption", True) and times[0] < 1.5
        maxc = cfg["hook_max_chars"] if hook else cfg["max_chars"]
        # BudouX で文節に分け、句読点を落としつつ文字位置と時刻を保持
        chunks, pos = [], 0
        for seg in parser.parse(text):
            chars = [(c, times[pos + k]) for k, c in enumerate(seg) if c not in "。、，,．."]
            pos += len(seg)
            while len(chars) > maxc:  # 長すぎる文節は強制分割
                chunks.append(chars[:maxc])
                chars = chars[maxc:]
            if chars:
                chunks.append(chars)
        lines, cur = [], []
        for ch in chunks:
            if cur and sum(len(c) for c in cur) + len(ch) > maxc:
                lines.append(cur)
                cur = []
            cur.append(ch)
        if cur:
            lines.append(cur)
        for k in range(0, len(lines), cfg["max_lines"]):
            group = lines[k:k + cfg["max_lines"]]
            caps.append({"lines": group, "hook": hook, "start": group[0][0][0][1],
                         "phrase_end": ph[-1]["end"]})
    # 表示時間: 次のテロップ開始まで（最短 min_duration・発話後 hold_after 秒残す）
    for i, c in enumerate(caps):
        nxt = caps[i + 1]["start"] if i + 1 < len(caps) else total
        end = min(nxt, c["phrase_end"] + cfg["hold_after"]) if i + 1 < len(caps) and \
            caps[i + 1]["start"] > c["phrase_end"] else nxt
        end = max(end, min(c["start"] + cfg["min_duration"], nxt))
        c["end"] = round(min(end, total), 3)
        c["start"] = round(c["start"], 3)
    return caps


def caption_html(i: int, c: dict, br: dict) -> tuple[str, list[tuple[str, float, str]]]:
    """テロップ 1 枚分の HTML と、(chunk id, 出現時刻, 種別) の一覧。
    一番長い行がセーフゾーン幅に収まるよう、文字サイズを自動で縮める。"""
    terms, cfg, sz = br["highlight_terms"], br["caption"], br["safe_zone"]
    anims, rows, widest = [], [], 0.0
    for li, line in enumerate(c["lines"]):
        spans = []
        for ci, chunk in enumerate(line):
            s = "".join(ch for ch, _ in chunk)
            mask = highlight_mask(s, terms)
            inner, k = "", 0
            while k < len(s):  # 同じ種別の連続文字をまとめて span 化
                j = k
                while j < len(s) and mask[j] == mask[k]:
                    j += 1
                seg = escape(s[k:j])
                inner += f'<span class="{mask[k]}">{seg}</span>' if mask[k] else seg
                k = j
            cid = f"c{i}-{li}-{ci}"
            kind = "price" if "price" in mask else ("hl" if "hl" in mask else "")
            anims.append((cid, chunk[0][1], kind))
            spans.append(f'<span class="chunk" id="{cid}">{inner}</span>')
        rows.append(f'<div class="line">{"".join(spans)}</div>')
        text = "".join(ch for chunk in line for ch, _ in chunk)
        m = highlight_mask(text, terms)
        widest = max(widest, sum(1.18 if k == "price" else (0.55 if ch.isascii() else 1.0)
                                 for ch, k in zip(text, m)) + 0.35)
    zone = W - sz["left"] - sz["right"]
    base = cfg["hook_font_size"] if c["hook"] else cfg["font_size"]
    fs = int(min(base, zone / max(widest, 1)))
    cls = "cap hook" if c["hook"] else "cap"
    dur = max(0.1, c["end"] - c["start"])
    html = (f'<div id="cap{i}" class="clip caplayer" data-start="{c["start"]:.3f}" '
            f'data-duration="{dur:.3f}" data-track-index="2"><div class="{cls}" style="font-size:{fs}px">'
            f'{"".join(rows)}</div></div>')
    return html, anims


def make_sfx(dst: Path) -> None:
    """自作の効果音（ライセンス問題なし）。sfx/ に同名ファイルを置けばそちらを優先。"""
    dst.mkdir(parents=True, exist_ok=True)
    recipes = {
        "pop.wav": "aevalsrc='0.7*sin(2*PI*(500+2600*t)*t)*exp(-28*t)':d=0.16:s=48000",
        "kira.wav": "aevalsrc='0.22*(sin(2*PI*2093*t)+sin(2*PI*3136*t)*0.8+sin(2*PI*4186*t)*0.6)"
                    "*exp(-5*t)*(0.6+0.4*sin(2*PI*18*t))':d=0.7:s=48000",
        "whoosh.wav": "anoisesrc=d=0.45:c=pink:a=0.6:r=48000,bandpass=f=1400:w=1200,"
                      "afade=t=in:d=0.25,afade=t=out:st=0.25:d=0.2",
    }
    for name, src in recipes.items():
        found = next((f for f in (STUDIO / "sfx").glob(name.split(".")[0] + ".*")), None)
        if found:
            shutil.copy2(found, dst / found.name)
            continue
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", src, "-ac", "2", dst / name])


def sfx_file(d: Path, base: str) -> str:
    f = next(d.glob(base + ".*"))
    return f"sfx/{f.name}"


def cmd_compose(a) -> None:
    p = Project(a.name)
    br, bf = brand(), p.brief
    cut = p.edit / "cut.mp4"
    if not cut.exists():
        sys.exit("先に ad cut を実行してください")
    total = ffprobe_duration(cut)
    words = load_json(p.edit / "timeline_words.json")
    caps = build_captions(words, br, bf, total, strict=p.state.get("engine") == "whisper")
    save_json(p.edit / "captions.json", [
        {"start": c["start"], "end": c["end"], "hook": c["hook"],
         "text": "\n".join("".join(ch for chunk in ln for ch, _ in chunk) for ln in c["lines"])}
        for c in caps])

    hf = p.hf
    hf.mkdir(parents=True, exist_ok=True)
    (hf / "fonts").mkdir(exist_ok=True)
    (hf / "vendor").mkdir(exist_ok=True)
    shutil.copy2(STUDIO / "fonts" / br["fonts"]["caption"], hf / "fonts/caption.ttf")
    shutil.copy2(STUDIO / "templates/vendor/gsap.min.js", hf / "vendor/gsap.min.js")
    shutil.copy2(cut, hf / "cut.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", cut, "-vn", "-c:a", "aac", "-b:a", "192k", hf / "voice.m4a"])
    make_sfx(hf / "sfx")
    if not (hf / "hyperframes.json").exists():
        save_json(hf / "hyperframes.json", {"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                                            "paths": {"assets": "assets"}})
        save_json(hf / "meta.json", {"id": p.name, "name": p.name})

    sz, col, cfg = br["safe_zone"], br["colors"], br["caption"]
    terms = br["highlight_terms"]
    sfxcfg = bf.get("sfx", {})
    vol = sfxcfg.get("volume", 0.45)
    cap_html, js, audio = [], [], []
    sfx_n = 0

    def add_sfx(name: str, t: float, v: float = vol) -> None:
        nonlocal sfx_n
        if not sfxcfg.get(name, True) or t >= total - 0.05:
            return
        f = hf / sfx_file(hf / "sfx", name)
        d = min(ffprobe_duration(f), total - t)
        audio.append(f'<audio id="sfx{sfx_n}" src="{sfx_file(hf / "sfx", name)}" data-start="{t:.3f}" '
                     f'data-duration="{d:.3f}" data-volume="{v}" data-track-index="{5 + sfx_n % 3}"></audio>')
        sfx_n += 1

    zoom = bf.get("punch_in", 1.08)
    for i, c in enumerate(caps):
        html, anims = caption_html(i, c, br)
        cap_html.append(html)
        kinds = {k for _, _, k in anims}
        for cid, t, kind in anims:
            ease = "back.out(2.4)" if c["hook"] else "back.out(1.8)"
            js.append(f'tl.fromTo("#{cid}",{{opacity:0,scale:0.55,y:26}},'
                      f'{{opacity:1,scale:1,y:0,duration:0.2,ease:"{ease}"}},{t:.3f});')
            if kind == "price":
                js.append(f'tl.fromTo("#{cid}",{{scale:1}},{{scale:1.12,duration:0.12,yoyo:true,repeat:1,'
                          f'ease:"power2.out"}},{t + 0.22:.3f});')
                add_sfx("kira", t)
        if c["hook"] and i == 0:
            add_sfx("pop", c["start"], vol * 1.2)
        elif kinds & {"hl"} and "price" not in kinds:
            add_sfx("pop", c["start"], vol * 0.8)
        if (kinds & {"hl", "price"} or c["hook"]) and zoom and zoom > 1:
            js.append(f'tl.fromTo("#main",{{scale:1}},{{scale:{zoom},duration:0.14,ease:"power2.out"}},{c["start"]:.3f});')
            js.append(f'tl.fromTo("#main",{{scale:{zoom}}},{{scale:1,duration:0.22,ease:"power2.inOut"}},'
                      f'{max(c["start"] + 0.15, c["end"] - 0.22):.3f});')

    cta = bf.get("cta")
    cta_html = ""
    if cta:
        cs = max(0.0, total - bf.get("cta_seconds", 3.0))
        cta_fs = int(min(54, (W - sz["left"] - sz["right"] - 60) / (len(cta) + 1.6)))
        cta_html = (f'<div id="ctalayer" class="clip" data-start="{cs:.3f}" data-duration="{total - cs:.3f}" '
                    f'data-track-index="3"><div id="cta" class="cta" style="font-size:{cta_fs}px">{escape(cta)}<span class="arrow">▶</span></div></div>')
        js.append(f'tl.fromTo("#cta",{{x:-900,opacity:0}},{{x:0,opacity:1,duration:0.35,ease:"power3.out"}},{cs:.3f});')
        js.append(f'tl.fromTo("#cta .arrow",{{x:0}},{{x:14,duration:0.3,yoyo:true,repeat:{int((total - cs) / 0.6)},'
                  f'ease:"sine.inOut"}},{cs + 0.4:.3f});')
        add_sfx("whoosh", max(0.0, cs - 0.05), vol * 0.9)

    bgm = bf.get("bgm")
    if bgm:
        src = (p.dir / bgm) if not Path(bgm).is_absolute() else Path(bgm)
        shutil.copy2(src, hf / ("bgm" + src.suffix))
        audio.append(f'<audio id="bgm" src="bgm{src.suffix}" data-start="0" data-duration="{total:.3f}" '
                     f'data-volume="{bf.get("bgm_volume", 0.12)}" data-fade-out="1" data-track-index="4"></audio>')

    logo = next((STUDIO / "brand").glob("logo.*"), None)
    logo_html = ""
    if logo and logo.suffix.lower() in {".png", ".svg", ".webp"}:
        shutil.copy2(logo, hf / ("logo" + logo.suffix))
        logo_html = (f'<div id="logolayer" class="clip" data-start="0" data-duration="{total:.3f}" '
                     f'data-track-index="4"><img id="logo" src="logo{logo.suffix}" alt=""></div>')

    stroke = col["stroke"]
    html = f"""<!doctype html>
<html lang="ja" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<script src="vendor/gsap.min.js"></script>
<style>
@font-face {{ font-family: "AdCaption"; src: url("fonts/caption.ttf") format("truetype"); font-weight: 900; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; font-family: "AdCaption", sans-serif; }}
#main {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; transform-origin: 50% 42%; }}
.caplayer, #ctalayer, #logolayer {{ position: absolute; inset: 0; pointer-events: none; }}
.cap {{ position: absolute; left: {sz["left"]}px; right: {sz["right"]}px; bottom: {sz["bottom"] + 40}px;
  display: flex; flex-direction: column; align-items: center; gap: 6px; }}
.cap.hook {{ bottom: auto; top: {sz["top"] + 140}px; }}
.line {{ white-space: nowrap; text-align: center; font-size: 1em; line-height: 1.25; font-weight: 900;
  color: {col["text"]}; -webkit-text-stroke: 14px {stroke}; paint-order: stroke fill;
  text-shadow: 0 6px 0 rgba(0,0,0,.35); letter-spacing: 0.02em; }}
.hook .line {{ -webkit-text-stroke: 16px {stroke}; }}
.chunk {{ display: inline-block; transform-origin: 50% 80%; }}
.hl {{ color: {col["highlight"]}; }}
.price {{ color: {col["price"]}; font-size: 1.18em; }}
.cta {{ position: absolute; left: {sz["left"]}px; right: {sz["right"]}px; top: {sz["top"] + 20}px;
  background: {col["navy"]}; color: #fff; border: 5px solid {col["highlight"]}; border-radius: 28px;
  font-weight: 900; text-align: center; white-space: nowrap; padding: 26px 20px; line-height: 1.25;
  box-shadow: 0 12px 30px rgba(0,0,0,.4); }}
.cta .arrow {{ display: inline-block; margin-left: 12px; color: {col["highlight"]}; }}
#logo {{ position: absolute; right: {sz["right"]}px; top: {sz["top"]}px; height: 72px; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{W}" data-height="{H}">
<video id="main" src="cut.mp4" muted playsinline data-start="0" data-duration="{total:.3f}" data-track-index="0"></video>
<audio id="voice" src="voice.m4a" data-start="0" data-duration="{total:.3f}" data-volume="1" data-track-index="1"></audio>
{chr(10).join(audio)}
{logo_html}
{chr(10).join(cap_html)}
{cta_html}
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
    log(f"コンポジション生成: {(hf / 'index.html').relative_to(p.dir)}（テロップ {len(caps)} 枚・SE {sfx_n} 個）")
    lint = subprocess.run([HF_BIN, "lint", str(hf)], capture_output=True, text=True)
    print(lint.stdout[-1500:] or lint.stderr[-1500:])
    p.set_state(composed=True)


# ---------------------------------------------------------------- render
def cmd_render(a) -> None:
    p = Project(a.name)
    p.output.mkdir(exist_ok=True)
    raw = p.edit / "render_raw.mp4"
    env = {**os.environ, "PRODUCER_BROWSER_GPU_MODE": os.environ.get("PRODUCER_BROWSER_GPU_MODE", "hardware")}
    run([HF_BIN, "render", p.hf, "-o", raw, "--fps", FPS, "-q", "draft" if a.draft else "delivery"], env=env)
    # 2パス loudnorm（-14 LUFS / TP -1）で SNS 向けに音量をそろえる
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    st = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
          f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true")
    secs = int(round(ffprobe_duration(raw)))
    final = p.output / f"{p.name}_{secs}s{'_draft' if a.draft else ''}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-c:v", "copy", "-af", af, "-ar", "48000",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])
    p.set_state(rendered=str(final))
    log(f"書き出し完了: {final.relative_to(STUDIO)}")


# -------------------------------------------------------------------- qa
def cmd_qa(a) -> None:
    p = Project(a.name)
    br = brand()
    final = Path(a.file) if a.file else Path(p.state.get("rendered", ""))
    if not final.exists():
        sys.exit("書き出し済みの動画がありません（ad render を先に）")
    qa = p.edit / "qa"
    shutil.rmtree(qa, ignore_errors=True)
    (qa / "frames").mkdir(parents=True)
    report, problems = [f"# QA レポート: {final.name}", f"- 検査日: {date.today()}", ""], []

    # 1) 仕様
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                    "stream=codec_type,width,height,r_frame_rate:format=duration,size",
                                    "-of", "json", str(final)], capture_output=True, text=True).stdout)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    dur, size = float(pr["format"]["duration"]), int(pr["format"]["size"]) / 1e6
    report += ["## 1. 仕様", f"- 解像度 {v['width']}×{v['height']} / {v['r_frame_rate']} fps / {dur:.2f} 秒 / {size:.1f} MB"]
    if (v["width"], v["height"]) != (W, H):
        problems.append("解像度が 1080×1920 ではありません")
    if size > 500:
        problems.append("ファイルが 500MB を超えています（TikTok 上限）")
    target = p.brief.get("target_seconds")
    if target and dur > target * 1.15:
        problems.append(f"尺 {dur:.1f}s が目標 {target}s を 15% 以上超過")

    # 2) フレーム（1秒ごと）＋セーフゾーン枠つきコンタクトシート
    sz = br["safe_zone"]
    box = f"drawbox=x={sz['left']}:y={sz['top']}:w={W - sz['left'] - sz['right']}:h={H - sz['top'] - sz['bottom']}:color=red@0.9:t=6"
    run(["ffmpeg", "-y", "-v", "error", "-i", final, "-vf", f"fps=1,{box},scale=540:960",
         qa / "frames/f_%03d.png"])
    n = len(list((qa / "frames").glob("*.png")))
    cols = 6
    run(["ffmpeg", "-y", "-v", "error", "-i", qa / "frames/f_%03d.png", "-vf",
         f"scale=270:480,tile={cols}x{(n + cols - 1) // cols}:padding=6:color=white", "-frames:v", "1",
         qa / "contact_sheet.png"])
    report += ["", "## 2. フレーム検査", f"- 1秒ごと {n} 枚: `edit/qa/frames/`",
               "- コンタクトシート（赤枠＝TikTok/リール共通セーフゾーン）: `edit/qa/contact_sheet.png`",
               "- テロップは生成時に赤枠内へ配置済み。はみ出し・文字切れは画像で目視/AI確認"]

    # 3) 音量
    eb = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", final, "-af", "ebur128=peak=true",
                         "-f", "null", "-"], capture_output=True, text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", eb)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", eb)
    li, tpk = float(I[-1]) if I else None, float(tp[-1]) if tp else None
    report += ["", "## 3. 音量", f"- 統合ラウドネス {li} LUFS（目標 -14 ±1） / トゥルーピーク {tpk} dBTP（≤ -1）"]
    if li is not None and abs(li + 14) > 1.5:
        problems.append(f"ラウドネス {li} LUFS が目標から外れています")
    if tpk is not None and tpk > -0.5:
        problems.append(f"トゥルーピーク {tpk} dBTP（音割れの恐れ）")

    # 4) 再文字起こし × テロップ照合
    caps = load_json(p.edit / "captions.json", [])
    cap_text = norm("".join(c["text"] for c in caps))
    report += ["", "## 4. テロップ照合（書き出し動画を再文字起こし）"]
    if WHISPER_MODEL.exists():
        words = transcribe_whisper(final, qa / "retranscribe.json")
        heard, _ = apply_glossary(*char_times(words), br["glossary"])
        heard = norm(heard)
        sm = difflib.SequenceMatcher(None, cap_text, heard)
        diffs = [(op, cap_text[i1:i2], heard[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
        report.append(f"- 一致率 {sm.ratio() * 100:.1f}%（音声認識側の誤りも含むので、差分を人/AIが判断）")
        for op, c_, h_ in diffs[:30]:
            report.append(f"  - テロップ「{c_ or '∅'}」 ⇔ 音声「{h_ or '∅'}」")
        if sm.ratio() < 0.85:
            problems.append("テロップと音声の一致率が 85% 未満")
    else:
        report.append("- Whisper モデル未導入のためスキップ")

    # 5) 表現チェック（景品表示法の注意語・表記ゆれ）
    report += ["", "## 5. 表現チェック（機械判定・最終判断は人）"]
    alltext = "\n".join(c["text"].replace("\n", "") for c in caps)
    hits = 0
    for ng in br["ng_expressions"]:
        for m in re.finditer(ng["pattern"], alltext):
            hits += 1
            report.append(f"- ⚠️「{m.group(0)}」: {ng['reason']}")
    for wrong, right in br["glossary"].items():
        if wrong in alltext:
            report.append(f"- ⚠️ 表記ゆれ「{wrong}」→「{right}」")
            hits += 1
    if not hits:
        report.append("- 注意語は検出されませんでした")
    problems += [f"注意表現 {hits} 件"] if hits else []

    report += ["", "## テロップ一覧"] + [f"- {c['start']:.2f}s {'[フック] ' if c['hook'] else ''}{c['text'].replace(chr(10), ' / ')}" for c in caps]
    report = report[:3] + ["## 判定", *(f"- ❌ {x}" for x in problems)] + (["- ✅ 自動チェックはすべて通過"] if not problems else []) + [""] + report[3:]
    out = p.output / "qa_report.md"
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report[:12]))
    log(f"QA レポート: {out.relative_to(STUDIO)} / コンタクトシート: {(qa / 'contact_sheet.png').relative_to(STUDIO)}")


# ------------------------------------------------------------------- all
def cmd_all(a) -> None:
    ns = argparse.Namespace(name=a.name, engine=None, force=False, draft=a.draft, file=None)
    cmd_transcribe(ns)
    p = Project(a.name)
    if not (p.edit / "edl.json").exists() or a.replan:
        cmd_plan(ns)
    if a.yes:
        cmd_approve(ns)
    if not Project(a.name).state.get("approved"):
        log("カット案で停止しました。edit/cut_plan.md を確認 → `ad approve " + a.name + "` → `ad all " + a.name + "`")
        return
    cmd_cut(ns)
    cmd_compose(ns)
    cmd_render(ns)
    cmd_qa(ns)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("new"); s.add_argument("name"); s.add_argument("--from", dest="from_files", nargs="*")
    s.add_argument("--move", action="store_true", help="コピーではなく移動")
    s = sp.add_parser("transcribe"); s.add_argument("name"); s.add_argument("--engine", choices=["auto", "scribe", "whisper"])
    s.add_argument("--force", action="store_true")
    s = sp.add_parser("plan"); s.add_argument("name")
    s = sp.add_parser("approve"); s.add_argument("name")
    s = sp.add_parser("cut"); s.add_argument("name"); s.add_argument("--force", action="store_true")
    s = sp.add_parser("compose"); s.add_argument("name")
    s = sp.add_parser("render"); s.add_argument("name"); s.add_argument("--draft", action="store_true")
    s = sp.add_parser("qa"); s.add_argument("name"); s.add_argument("--file")
    s = sp.add_parser("all"); s.add_argument("name"); s.add_argument("--yes", action="store_true", help="カット案を自動承認")
    s.add_argument("--draft", action="store_true"); s.add_argument("--replan", action="store_true")
    a = ap.parse_args()
    {"new": cmd_new, "transcribe": cmd_transcribe, "plan": cmd_plan, "approve": cmd_approve, "cut": cmd_cut,
     "compose": cmd_compose, "render": cmd_render, "qa": cmd_qa, "all": cmd_all}[a.cmd](a)


if __name__ == "__main__":
    main()
