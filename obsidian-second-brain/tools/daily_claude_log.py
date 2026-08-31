#!/usr/bin/env python3
"""その日の Claude Code 活動を、Obsidian のデイリーノートに追記する。

`claude_code_import.py` が「1セッション=1ノート」で全文を保存するのに対し、
こちらは「その日に何をやったか」の一覧をデイリーノート（10_Daily/YYYY-MM-DD.md）に
1セクションとして書き込む。何度実行しても同じセクションを置き換えるだけ（冪等）。

使い方:
    python3 tools/daily_claude_log.py                 # 今日
    python3 tools/daily_claude_log.py --date 2026-08-27
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from claude_code_import import clean_title, extract_text, is_noise  # noqa: E402

JST = timezone(timedelta(hours=9))
SECTION = "## 🤖 Claude Code 活動ログ"
MARK_END = "<!-- /claude-code-log -->"


def jst(ts: str):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(JST)
    except (ValueError, TypeError):
        return None


def scan(projects: Path, day: str):
    """その日に発言のあったセッションを集める（session_id で名寄せ）。"""
    merged = {}
    for f in sorted(projects.rglob("*.jsonl")):
        first = last = None
        title = ""
        cwd = ""
        n_user = n_asst = 0
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = jst(d.get("timestamp", ""))
            if not t or t.strftime("%Y-%m-%d") != day:
                continue
            cwd = cwd or d.get("cwd", "")
            typ = d.get("type")
            if typ not in ("user", "assistant"):
                continue
            text = extract_text((d.get("message") or {}).get("content"))
            if not text or is_noise(text):
                continue
            first = first or t
            last = t
            if typ == "user":
                n_user += 1
                if not title:
                    title = clean_title(text)
            else:
                n_asst += 1
        if not (first and (n_user or n_asst)):
            continue
        # 同じ session_id が複数の作業ディレクトリに現れることがある（cwd 変更時）。
        # 二重計上を避けるため、session_id で1件にまとめる。
        prev = merged.get(f.stem)
        if prev:
            prev["start"] = min(prev["start"], first)
            prev["end"] = max(prev["end"], last)
            prev["n_user"] += n_user
            prev["n_asst"] += n_asst
            prev["title"] = prev["title"] or title
            prev["cwd"] = prev["cwd"] or cwd
        else:
            merged[f.stem] = {
                "session_id": f.stem, "title": title or "Claude Codeセッション",
                "cwd": cwd, "start": first, "end": last,
                "n_user": n_user, "n_asst": n_asst,
            }
    return sorted(merged.values(), key=lambda s: s["start"])


def note_for(session_id: str, notes_dir: Path):
    """取り込み済みノートを session_id で探し、ウィキリンク名を返す。"""
    for p in notes_dir.glob("*.md"):
        head = p.read_text(encoding="utf-8", errors="ignore")[:600]
        if f"session_id: {session_id}" in head:
            return p.stem
    return None


def build(sessions, notes_dir: Path, day: str) -> str:
    if not sessions:
        return f"{SECTION}\n\n- この日は Claude Code の利用なし。\n\n{MARK_END}"
    lines = [SECTION, "",
             f"> {day} のセッション {len(sessions)} 件（`tools/daily_claude_log.py` が自動生成）。", ""]
    for s in sessions:
        span = f"{s['start']:%H:%M}–{s['end']:%H:%M}"
        proj = Path(s["cwd"]).name or "(不明)"
        link = note_for(s["session_id"], notes_dir)
        head = f"[[{link}|{s['title']}]]" if link else s["title"]
        lines.append(f"- **{span}** {head}")
        lines.append(f"    - 作業場所: `{proj}` / やり取り: {s['n_user']}往復")
    lines += ["", MARK_END]
    return "\n".join(lines)


def ensure_daily(path: Path, day: str, templates: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    tpl = templates / "デイリーノート.md"
    d = datetime.strptime(day, "%Y-%m-%d")
    body = tpl.read_text(encoding="utf-8") if tpl.exists() else "---\ntitle: \"{{date}}\"\n---\n\n# {{date}}\n"
    body = (body.replace("{{date}}", day)
                .replace("{{yesterday}}", (d - timedelta(days=1)).strftime("%Y-%m-%d"))
                .replace("{{tomorrow}}", (d + timedelta(days=1)).strftime("%Y-%m-%d")))
    path.write_text(body, encoding="utf-8")
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(JST).strftime("%Y-%m-%d"))
    ap.add_argument("--vault", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--projects", default=str(Path.home() / ".claude" / "projects"))
    a = ap.parse_args()

    vault = Path(a.vault)
    projects = Path(a.projects)
    if not projects.exists():
        print(f"[skip] {projects} が無い"); return 0

    sessions = scan(projects, a.date)
    section = build(sessions, vault / "40_Resources" / "ClaudeCode", a.date)

    daily = vault / "10_Daily" / f"{a.date}.md"
    daily.parent.mkdir(parents=True, exist_ok=True)
    created = not daily.exists()
    body = ensure_daily(daily, a.date, vault / "90_Templates")

    # 既存セクションがあれば置き換え、無ければ「🔗 関連」の直前、それも無ければ末尾に追加
    if SECTION in body:
        body = re.sub(re.escape(SECTION) + r".*?" + re.escape(MARK_END), section, body, flags=re.S)
    elif "## 🔗 関連" in body:
        body = body.replace("## 🔗 関連", section + "\n\n## 🔗 関連")
    else:
        body = body.rstrip() + "\n\n" + section + "\n"

    # frontmatter の updated を実行日に合わせる（created は触らない）
    body = re.sub(r"(?m)^updated: .*$", f"updated: {a.date}", body, count=1)
    daily.write_text(body, encoding="utf-8")

    print(f"[done] {a.date}: セッション {len(sessions)} 件 → {daily.relative_to(vault)}"
          f"{' (新規作成)' if created else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
