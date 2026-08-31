#!/usr/bin/env python3
"""Claude Code のセッション記録 (~/.claude/projects/**/*.jsonl) を Obsidian ノートに変換する。

claude.ai のブラウザ会話とは別に、Claude Code（CLI）のローカルセッション記録を取り込む。
1 セッション(.jsonl) = 1 Markdown ノートとして `40_Resources/ClaudeCode/` に書き出す。

使い方:
    # 既定: ~/.claude/projects 以下を全部
    python3 tools/claude_code_import.py
    # ファイル/ディレクトリを指定
    python3 tools/claude_code_import.py ~/.claude/projects --out 40_Resources/ClaudeCode

抽出方針:
- user / assistant の "テキスト" だけを残す（tool_use / tool_result / thinking は除外）。
- システム注入（<system-reminder> 等）や環境メタは除外し、対話本文のみ保存。
- セッション uuid で既存ファイルを判定してスキップ（再実行しても重複しない）。
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

INVALID = re.compile(r'[\\/:*?"<>|#\^\[\]]')
NOISE_PREFIXES = ("<system-reminder", "<command-", "Caveat:", "<local-command")


URL_RE = re.compile(r"https?://\S+")
# 先頭のリスト記号・引用符・空白
LEAD_RE = re.compile(r"^[\s*\-–—•>\u3000\[\]\(\)「」『』\"\']+")
# 本文と関係ないUIの決まり文句
CHATTER_RE = re.compile(
    r"(実行済み\s*\d+\s*件のコマンド"
    r"|使用済み\s*\d+\s*個のツール"
    r"|読み取り\s*\d+\s*個のファイル"
    r"|The user hasn't given a task yet"
    r"|Caveat:.*)",
    re.I,
)


def clean_title(text: str) -> str:
    """セッション冒頭の発言から、ファイル名・タイトルに使える短い日本語を作る。"""
    t = URL_RE.sub(" ", text or "")      # URLは丸ごと落とす（長く意味が無いため）
    t = CHATTER_RE.sub(" ", t)           # UIの定型文を落とす
    t = re.sub(r"\s+", " ", t)
    t = LEAD_RE.sub("", t).strip()
    # 最初の文（句点・改行・ピリオド）までを見出しにする
    m = re.split(r"[。\n]|(?<=[a-z])\. ", t)
    first = (m[0] if m else t).strip()
    if len(first) >= 8:
        t = first
    return t[:60].strip()


def slugify(title: str, fallback: str) -> str:
    title = INVALID.sub("", (title or "").strip())
    title = re.sub(r"\s+", "_", title).strip("_")   # ファイル名に空白を入れない
    return title[:60] or fallback


def to_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(value)[:10]


def extract_text(content) -> str:
    """message.content（str か block配列）から人間可読テキストのみを取り出す。"""
    if isinstance(content, str):
        return content.strip()
    parts = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        # tool_use / tool_result / thinking / image は除外
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def is_noise(text: str) -> bool:
    t = text.lstrip()
    if not t:
        return True
    return t.startswith(NOISE_PREFIXES)


def parse_session(path: Path):
    """1 つの jsonl を読み、(meta, turns) を返す。turns=[(role, text), ...]"""
    meta = {"session_id": path.stem, "cwd": "", "git_branch": "", "first": "", "last": ""}
    turns = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("type") not in ("user", "assistant"):
            continue
        msg = o.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        text = extract_text(msg.get("content"))
        if not text or (role == "user" and is_noise(text)):
            continue
        ts = to_date(o.get("timestamp"))
        if ts:
            meta["first"] = meta["first"] or ts
            meta["last"] = ts
        meta["cwd"] = meta["cwd"] or o.get("cwd", "")
        meta["git_branch"] = meta["git_branch"] or o.get("gitBranch", "")
        turns.append((role, text))
    return meta, turns


def render(meta: dict, turns: list) -> tuple[str, str, str]:
    first_user = next((t for r, t in turns if r == "user"), "") or ""
    title = clean_title(first_user) or "Claude Codeセッション"
    created = meta["first"] or "0000-00-00"
    fname = f"{created}-{slugify(title, meta['session_id'][:8])}.md"
    lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f"created: {created}",
        f"updated: {meta['last'] or created}",
        f"session_id: {meta['session_id']}",
        f"tags: [claude-code, resource]",
        "type: resource",
        "status: active",
        "source: claude-code",
        f'cwd: "{meta["cwd"]}"',
        f"git_branch: {meta['git_branch']}",
        "---",
        "",
        f"# {title}",
        "",
        f"> Claude Code セッション記録（{created} 〜 {meta['last'] or created}）。ツール実行ログは除外。",
        "",
    ]
    for role, text in turns:
        who = "**あなた**" if role == "user" else "**Claude**"
        lines += [f"### {who}", "", text, ""]
    return fname, "\n".join(lines), title


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default=str(Path.home() / ".claude" / "projects"),
                    help="jsonl ファイル or ディレクトリ（既定 ~/.claude/projects）")
    ap.add_argument("--out", default="40_Resources/ClaudeCode", help="出力フォルダ")
    args = ap.parse_args()

    src = Path(args.input).expanduser()
    if src.is_dir():
        files = sorted(src.rglob("*.jsonl"))
    elif src.is_file():
        files = [src]
    else:
        print(f"[error] 入力が見つかりません: {src}", file=sys.stderr)
        return 1
    if not files:
        print(f"[warn] jsonl が見つかりません: {src}")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # 既存ノートを session_id で索引する。ファイル名ではなく session_id で判定するため、
    # タイトル生成規則を変えても同じセッションが二重取り込みされない。
    existing = {}
    for md in out.glob("*.md"):
        head = md.read_text(encoding="utf-8", errors="ignore")[:600]
        m = re.search(r"(?m)^session_id: (\S+)", head)
        if m:
            existing[m.group(1)] = md

    written = skipped = empty = 0
    index = []
    for path in files:
        meta, turns = parse_session(path)
        if not turns:
            empty += 1
            continue
        fname, body, title = render(meta, turns)
        prev = existing.get(meta["session_id"])
        if prev:
            # 既に取り込み済み。手で付け直したファイル名を尊重し、索引もそちらを指す。
            index.append((meta["first"], title, prev.name))
            skipped += 1
            continue
        index.append((meta["first"], title, fname))
        dest = out / fname
        if dest.exists():
            skipped += 1
            continue
        dest.write_text(body, encoding="utf-8")
        existing[meta["session_id"]] = dest
        written += 1

    index.sort(reverse=True)
    idx = ["---", "title: ClaudeCode索引", "tags: [claude-code, index, meta]",
           "type: resource", "---", "", "# Claude Code セッション索引", "",
           f"取り込み {len(index)} 件（新規 {written} / 既存 {skipped} / 本文なし {empty}）。"
           f"最終更新 {datetime.now().strftime('%Y-%m-%d')}", ""]
    for created, title, fname in index:
        idx.append(f"- {created or '----'} [[{fname[:-3]}|{title}]]")
    (out / "_ClaudeCode索引.md").write_text("\n".join(idx) + "\n", encoding="utf-8")

    print(f"[done] 新規 {written} / スキップ {skipped} / 本文なし {empty} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
