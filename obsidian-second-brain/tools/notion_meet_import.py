#!/usr/bin/env python3
"""Notion AI Notetaker の会議ノートを Obsidian の会議ノートに取り込む。

Google Meet / Zoom の会議を Notion AI Notetaker が録音・文字起こし・要約し、
その結果が Notion のデータベース（例: "Meeting Notes"）に溜まる。
このスクリプトは Notion API でそのDBを見て、まだ取り込んでいない会議ページだけを
`15_Meetings/YYYY-MM-DD-会議名.md` に変換する（再実行しても重複しない）。

依存: 標準ライブラリのみ（urllib）。requests は不要。

設定（どちらか）:
  1) 環境変数  NOTION_TOKEN, NOTION_MEETINGS_DB_ID
  2) 設定ファイル tools/notion_config.local.json（.gitignore 済み）
        {"token": "ntn_xxx", "database_id": "xxxxxxxx..."}

使い方:
    python3 tools/notion_meet_import.py               # 前回同期以降の新着だけ
    python3 tools/notion_meet_import.py --all          # 全ページを対象（初回など）
    python3 tools/notion_meet_import.py --since 2026-09-01
    python3 tools/notion_meet_import.py --dry-run      # 書き込まず対象だけ表示

取り込み方針:
- Notion AI Notetaker が生成した「要約 / メモ / 文字起こし」本文をそのまま Obsidian の
  会議ノートに落とす（憶測で内容を創作しない）。原文の Notion ページURLも残す。
- ページ本文から meet.google.com / zoom.us を検出して source と tags を切り替える。
- Notion ページID で取り込み済みを判定（.notion-sync-state.json）。
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
JST = timezone(timedelta(hours=9))

VAULT = Path(__file__).resolve().parent.parent          # obsidian-second-brain/
MEETINGS_DIR = VAULT / "15_Meetings"
STATE_PATH = MEETINGS_DIR / ".notion-sync-state.json"
CONFIG_PATH = Path(__file__).resolve().parent / "notion_config.local.json"

INVALID = re.compile(r'[\\/:*?"<>|#\^\[\]]')


# ----------------------------------------------------------------------------
# 設定・状態
# ----------------------------------------------------------------------------
def load_config():
    """トークンとDB IDを、環境変数 → 設定ファイル の順で読む。"""
    import os
    token = os.environ.get("NOTION_TOKEN")
    db_id = os.environ.get("NOTION_MEETINGS_DB_ID")
    if (not token or not db_id) and CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        token = token or cfg.get("token")
        db_id = db_id or cfg.get("database_id")
    if not token or not db_id:
        sys.exit(
            "エラー: Notion のトークン/DB ID が未設定です。\n"
            f"  {CONFIG_PATH} を作成し、次を記入してください:\n"
            '  {"token": "ntn_...", "database_id": "..."}\n'
            "  （または環境変数 NOTION_TOKEN / NOTION_MEETINGS_DB_ID を設定）"
        )
    return token, db_id.replace("-", "")


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_synced": None, "synced_page_ids": []}


def save_state(state):
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ----------------------------------------------------------------------------
# Notion API（標準ライブラリのみ）
# ----------------------------------------------------------------------------
def api(token, method, path, payload=None):
    url = f"{NOTION_API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        sys.exit(f"Notion API エラー {e.code}: {body[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"Notion API 接続エラー: {e}")


def query_database(token, db_id, since_iso=None):
    """DBのページを新しい順に取得。since_iso があれば last_edited_time で絞る。"""
    pages, cursor = [], None
    body = {
        "page_size": 100,
        "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
    }
    if since_iso:
        body["filter"] = {
            "timestamp": "last_edited_time",
            "last_edited_time": {"on_or_after": since_iso},
        }
    while True:
        if cursor:
            body["start_cursor"] = cursor
        res = api(token, "POST", f"/databases/{db_id}/query", body)
        pages.extend(res.get("results", []))
        if res.get("has_more"):
            cursor = res.get("next_cursor")
        else:
            break
    return pages


def get_blocks(token, block_id):
    """ブロックの子を全部取得（ページ本文）。"""
    blocks, cursor = [], None
    while True:
        q = f"?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        res = api(token, "GET", f"/blocks/{block_id}/children{q}")
        blocks.extend(res.get("results", []))
        if res.get("has_more"):
            cursor = res.get("next_cursor")
        else:
            break
    return blocks


# ----------------------------------------------------------------------------
# Notion → Markdown 変換
# ----------------------------------------------------------------------------
def rich_text(rt):
    """rich_text 配列を Markdown 文字列に。"""
    out = []
    for r in rt or []:
        t = r.get("plain_text", "")
        ann = r.get("annotations", {})
        if ann.get("code"):
            t = f"`{t}`"
        if ann.get("bold"):
            t = f"**{t}**"
        if ann.get("italic"):
            t = f"*{t}*"
        href = r.get("href")
        if href:
            t = f"[{t}]({href})"
        out.append(t)
    return "".join(out)


def blocks_to_markdown(token, blocks, depth=0):
    """Notion ブロック列を Markdown に。主要ブロック型を対応。"""
    lines = []
    indent = "  " * depth
    for b in blocks:
        bt = b.get("type")
        data = b.get(bt, {})
        text = rich_text(data.get("rich_text")) if isinstance(data, dict) else ""
        if bt == "paragraph":
            lines.append(indent + text if text else "")
        elif bt in ("heading_1", "heading_2", "heading_3"):
            level = {"heading_1": "##", "heading_2": "###", "heading_3": "####"}[bt]
            lines.append(f"{level} {text}")
        elif bt == "bulleted_list_item":
            lines.append(f"{indent}- {text}")
        elif bt == "numbered_list_item":
            lines.append(f"{indent}1. {text}")
        elif bt == "to_do":
            mark = "x" if data.get("checked") else " "
            lines.append(f"{indent}- [{mark}] {text}")
        elif bt == "toggle":
            lines.append(f"{indent}- {text}")
        elif bt == "quote":
            lines.append(f"> {text}")
        elif bt == "callout":
            emoji = (data.get("icon") or {}).get("emoji", "")
            lines.append(f"> {emoji} {text}".rstrip())
        elif bt == "code":
            lang = data.get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        elif bt == "divider":
            lines.append("---")
        elif bt == "table_of_contents":
            continue
        else:
            if text:
                lines.append(indent + text)
        # 子ブロックを再帰的に
        if b.get("has_children") and bt not in ("code",):
            children = get_blocks(token, b["id"])
            child_md = blocks_to_markdown(token, children, depth + 1)
            if child_md:
                lines.append(child_md)
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# ページのプロパティ抽出（スキーマに依存しすぎない）
# ----------------------------------------------------------------------------
def extract_title(props):
    for name, p in props.items():
        if p.get("type") == "title":
            return rich_text(p.get("title")) or "無題の会議"
    return "無題の会議"


def extract_date(props, fallback_iso):
    for name, p in props.items():
        if p.get("type") == "date" and p.get("date"):
            return p["date"].get("start") or fallback_iso
    return fallback_iso


def extract_attendees(props):
    people = []
    for name, p in props.items():
        t = p.get("type")
        if t == "people":
            people += [x.get("name", "") for x in p.get("people", [])]
        elif t == "multi_select" and name.lower() in (
            "attendees", "participants", "参加者", "people"
        ):
            people += [x.get("name", "") for x in p.get("multi_select", [])]
    return [x for x in people if x]


def to_date(value, fallback=""):
    if not value:
        return fallback
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(JST).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(value)[:10] or fallback


def slugify(title):
    t = INVALID.sub("", (title or "").strip())
    t = re.sub(r"\s+", "_", t).strip("_")
    return t[:50] or "会議"


def detect_source(body_text, page_url):
    text = (body_text or "") + " " + (page_url or "")
    if "zoom.us" in text:
        return "zoom", ["meeting", "zoom", "notion"]
    if "meet.google.com" in text:
        return "google-meet", ["meeting", "meet", "notion"]
    return "notion", ["meeting", "notion"]


# ----------------------------------------------------------------------------
# ノート生成
# ----------------------------------------------------------------------------
def build_note(title, date, attendees, source, tags, page_url, body_md):
    today = datetime.now(JST).strftime("%Y-%m-%d")
    yaml_tags = "[" + ", ".join(tags) + "]"
    yaml_att = "[" + ", ".join(f'"{a}"' for a in attendees) + "]"
    fm = [
        "---",
        f'title: "{date} {title}"',
        f"created: {today}",
        f"updated: {today}",
        f"tags: {yaml_tags}",
        "type: resource",
        "status: active",
        f"date: {date}",
        f"source: {source}",
        f"notion_url: {page_url}",
        f"attendees: {yaml_att}",
        "---",
        "",
        f"# {date} {title}",
        "",
        f"- **日時**: {date}",
        f"- **参加者**: {', '.join(attendees) if attendees else '（未取得）'}",
        f"- **Notion 原文**: {page_url}",
        "",
        "> ℹ️ この議事録は Notion AI Notetaker の記録を自動取り込みしたものです。",
        "",
        "## 📝 内容（Notion より）",
        "",
        body_md.strip() if body_md.strip() else "（本文なし）",
        "",
        "## ☑️ アクションアイテム",
        "- [ ] （担当 / 期限）",
        "",
        "## 🔗 関連",
        "- [[]]",
        "",
    ]
    return "\n".join(fm)


# ----------------------------------------------------------------------------
# メイン
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全ページを対象にする")
    ap.add_argument("--since", help="この日付以降の更新のみ (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="書き込まず対象だけ表示")
    args = ap.parse_args()

    token, db_id = load_config()
    state = load_state()
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)

    # 対象期間の決定
    since_iso = None
    if args.since:
        since_iso = f"{args.since}T00:00:00+09:00"
    elif not args.all and state.get("last_synced"):
        since_iso = state["last_synced"]

    pages = query_database(token, db_id, since_iso)
    synced = set(state.get("synced_page_ids", []))

    created, skipped = [], 0
    for page in pages:
        pid = page["id"].replace("-", "")
        if pid in synced:
            skipped += 1
            continue

        props = page.get("properties", {})
        title = extract_title(props)
        created_time = page.get("created_time")
        date = to_date(extract_date(props, created_time), to_date(created_time))
        attendees = extract_attendees(props)
        page_url = page.get("url", "")

        blocks = get_blocks(token, page["id"])
        body_md = blocks_to_markdown(token, blocks)
        source, tags = detect_source(body_md, page_url)

        fname = f"{date}-{slugify(title)}.md"
        fpath = MEETINGS_DIR / fname
        # 同名衝突は連番で回避
        n = 2
        while fpath.exists():
            fpath = MEETINGS_DIR / f"{date}-{slugify(title)}-{n}.md"
            n += 1

        note = build_note(title, date, attendees, source, tags, page_url, body_md)
        if args.dry_run:
            print(f"[dry-run] {fpath.name}  (source={source}, chars={len(body_md)})")
        else:
            fpath.write_text(note, encoding="utf-8")
            print(f"作成: {fpath.name}  (source={source})")
        created.append(pid)

    # 状態更新（dry-run では更新しない）
    if not args.dry_run:
        state["last_synced"] = datetime.now(JST).isoformat(timespec="seconds")
        state["synced_page_ids"] = list(synced | set(created))
        save_state(state)

    print(
        f"\n完了: 新規 {len(created)} 件 / スキップ(取込済) {skipped} 件"
        f"{'  ※dry-run: 書き込みなし' if args.dry_run else ''}"
    )


if __name__ == "__main__":
    main()
