#!/usr/bin/env python3
"""Deterministic lint for the second-brain vault.

Reports what a script can know for certain, so the model's lint pass starts
from facts instead of re-deriving them: dead [[wikilinks]], compiled pages
missing a source link back to raw/, pages past their `expires:` date, and
likely-duplicate page titles.

Usage:
    python3 lint.py [VAULT_DIR]     # default: parent of this script's dir
Exit code is 0 always (this is a report, not a gate). Writes the same report
to scripts/.lint-report.txt so the model pass can read it.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
COMPILED_DIRS = ("entities", "concepts")
# Only these hold real vault content. templates/ and scripts/ carry example
# links and prompts that must not be linted as if they were knowledge pages.
CONTENT_DIRS = ("entities", "concepts", "raw", "synthesis")


def vault_dir() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    return Path(__file__).resolve().parent.parent


def md_files(root: Path) -> list[Path]:
    """Vault content pages only: INDEX.md plus the content dirs, no READMEs."""
    out: list[Path] = []
    index = root / "INDEX.md"
    if index.exists():
        out.append(index)
    for d in CONTENT_DIRS:
        for p in (root / d).rglob("*.md"):
            if ".git" in p.parts or p.name == "README.md":
                continue
            out.append(p)
    return out


def norm_target(target: str) -> str:
    """Normalize a wikilink target to a comparable key (basename, no .md)."""
    t = target.strip().replace("\\", "/")
    if t.endswith(".md"):
        t = t[:-3]
    return t.split("/")[-1].lower()


def front_matter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end]
    return ""


def main() -> int:
    root = vault_dir()
    files = md_files(root)

    # Build the set of link targets that exist (by basename, lowercased).
    existing: set[str] = set()
    for p in files:
        existing.add(p.stem.lower())

    dead_links: list[str] = []
    missing_source: list[str] = []
    expired: list[str] = []
    titles: dict[str, list[str]] = {}

    today = date.today()

    for p in files:
        if p.name == "README.md":
            continue
        rel = p.relative_to(root)
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = front_matter(text)

        # Dead links (ignore links inside HTML comments — those are format hints)
        for m in WIKILINK.finditer(HTML_COMMENT.sub("", text)):
            key = norm_target(m.group(1))
            if key and key not in existing:
                dead_links.append(f"{rel}: [[{m.group(1)}]]")

        # Compiled pages must cite raw/
        if rel.parts and rel.parts[0] in COMPILED_DIRS:
            has_source = "raw/" in text or re.search(r"\[\[raw[/\\]", text)
            if not has_source:
                missing_source.append(str(rel))

            # duplicate-title detection within compiled dirs
            titles.setdefault(p.stem.lower(), []).append(str(rel))

        # Expiry
        m = re.search(r"^expires:\s*(\d{4}-\d{2}-\d{2})", fm, re.MULTILINE)
        if m:
            try:
                y, mo, d = (int(x) for x in m.group(1).split("-"))
                if date(y, mo, d) < today:
                    expired.append(f"{rel} (expired {m.group(1)})")
            except ValueError:
                pass

    dupes = {k: v for k, v in titles.items() if len(v) > 1}

    lines: list[str] = []

    def section(title: str, items: list[str]) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.extend(f"  - {it}" for it in items) if items else lines.append("  (none)")
        lines.append("")

    lines.append(f"# Vault lint report — {today.isoformat()}")
    lines.append(f"Vault: {root}")
    lines.append(f"Markdown files scanned: {len(files)}")
    lines.append("")
    section("Dead wikilinks", dead_links)
    section("Compiled pages missing a raw/ source", missing_source)
    section("Expired pages (past expires:)", expired)
    section(
        "Likely duplicate titles",
        [f"{k}: {', '.join(v)}" for k, v in dupes.items()],
    )

    report = "\n".join(lines)
    print(report)
    (Path(__file__).resolve().parent / ".lint-report.txt").write_text(
        report, encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
