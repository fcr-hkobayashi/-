#!/usr/bin/env python3
"""claude.ai のデータエクスポート (conversations.json) を Obsidian ノートに変換する。

claude.ai → Settings → Privacy → Export data で届くメール内 zip の `conversations.json`
を入力に、1 会話 = 1 Markdown ファイルとして `40_Resources/ClaudeChats/` に書き出す。

使い方:
    python3 tools/claude_chat_import.py <conversations.json> [--out 40_Resources/ClaudeChats]

特徴:
- 会話ごとに frontmatter（title/created/updated/uuid/tags/type）を付与
- 発話は **あなた** / **Claude** で整形
- 既存ファイルは uuid で判定してスキップ（再実行しても重複しない）
- 取り込み一覧の索引ノート `_ClaudeChats索引.md` を生成
- 本文の改変・要約はしない（生ログを忠実に保存）。要約は Obsidian 側で /permanent 等に任せる
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

INVALID = re.compile(r'[\\/:*?"<>|#\^\[\]]')


def slugify(title: str, fallback: str) -> str:
    title = (title or "").strip()
    if not title:
        title = fallback
    title = INVALID.sub("", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:80] or fallback


def to_date(value: str) -> str:
    """ISO8601 文字列 → YYYY-MM-DD。失敗時は空文字。"""
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(value)[:10]


def message_text(msg: dict) -> str:
    """chat_messages の 1 件からテキストを取り出す。text / content[] 両対応。"""
    if isinstance(msg.get("text"), str) and msg["text"].strip():
        return msg["text"].strip()
    parts = []
    for block in msg.get("content", []) or []:
        if isinstance(block, dict):
            if block.get("type") == "text" and block.get("text"):
                parts.append(block["text"])
            elif block.get("text"):
                parts.append(block["text"])
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def render(conv: dict) -> tuple[str, str, str]:
    """会話 dict → (ファイル名, Markdown 本文, 表示タイトル)。"""
    uuid = conv.get("uuid") or conv.get("id") or ""
    title = conv.get("name") or conv.get("title") or "無題の会話"
    created = to_date(conv.get("created_at"))
    updated = to_date(conv.get("updated_at")) or created
    fname = f"{created or '0000-00-00'}-{slugify(title, uuid[:8] or 'chat')}.md"

    lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f"created: {created}",
        f"updated: {updated}",
        f"uuid: {uuid}",
        "tags: [claude-chat, resource]",
        "type: resource",
        "status: active",
        "source: claude.ai",
        "---",
        "",
        f"# {title}",
        "",
        f"> claude.ai の会話ログ（エクスポート由来）。作成 {created} / 更新 {updated}",
        "",
    ]
    messages = conv.get("chat_messages") or conv.get("messages") or []
    for msg in messages:
        sender = (msg.get("sender") or msg.get("role") or "").lower()
        who = "**あなた**" if sender in ("human", "user") else "**Claude**"
        body = message_text(msg)
        if not body:
            continue
        lines.append(f"### {who}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return fname, "\n".join(lines), title


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="conversations.json のパス")
    ap.add_argument("--out", default="40_Resources/ClaudeChats", help="出力フォルダ")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[error] 入力ファイルが見つかりません: {src}", file=sys.stderr)
        return 1

    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[error] JSON を解析できません: {exc}", file=sys.stderr)
        return 1

    conversations = data if isinstance(data, list) else data.get("conversations", [data])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written, skipped, index = 0, 0, []
    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        fname, body, title = render(conv)
        dest = out / fname
        if dest.exists():
            skipped += 1
            index.append((to_date(conv.get("created_at")), title, fname))
            continue
        dest.write_text(body, encoding="utf-8")
        written += 1
        index.append((to_date(conv.get("created_at")), title, fname))

    # 索引ノート
    index.sort(reverse=True)
    idx_lines = [
        "---",
        "title: Claude会話 索引",
        "tags: [claude-chat, index, meta]",
        "type: resource",
        "---",
        "",
        "# Claude会話 索引",
        "",
        f"取り込み {len(index)} 会話（新規 {written} / 既存 {skipped}）。最終更新: "
        + datetime.now().strftime("%Y-%m-%d"),
        "",
    ]
    for created, title, fname in index:
        idx_lines.append(f"- {created or '----'} [[{fname[:-3]}|{title}]]")
    (out / "_ClaudeChats索引.md").write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

    print(f"[done] 新規 {written} 件 / スキップ（既存）{skipped} 件 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
