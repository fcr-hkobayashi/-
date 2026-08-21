# Second Brain — Agent Operating Manual

This folder is a knowledge base, not an app. Treat it like a codebase: the
markdown files are the source, you are the programmer, and Obsidian is the
editor the human uses to read what you write. Your job is **compiling** — you
read raw material and turn it into linked, deduplicated wiki pages.

## The four pieces

| Folder / file  | What lives here | Your permission |
| -------------- | --------------- | --------------- |
| `raw/`         | Everything captured untouched: articles, transcripts, call notes, competitor pages, exports. Ground truth. | **Read-only. Never edit or delete.** |
| `entities/`    | One page per concrete thing: a client, a competitor, a tool, a person. | Read + write |
| `concepts/`    | One page per idea: a strategy, a pattern, a lesson. | Read + write |
| `INDEX.md`     | The front door: every entity and concept listed with a one-line description, so you know what exists without opening everything. | Read + write |

`templates/`, `scripts/`, and `synthesis/` support the system — see the README.

## Writing rules (non-negotiable)

1. **One lesson/thing per file**, with a one-line `summary:` at the top.
2. **Update the existing page** instead of creating a duplicate. Search
   `INDEX.md` and the relevant folder first.
3. **Delete notes that turn out to be wrong.** A confidently wrong page is
   worse than a missing one.
4. **Keep raw sources and compiled pages separate, always.** Never paste raw
   dumps into an entity/concept page — link back to the `raw/` file instead.
5. **Every compiled page must carry at least one source link** back into
   `raw/` (a `[[wikilink]]` or relative path). A page with no source is a
   claim, not knowledge — flag it, don't trust it.
6. **Link generously.** Every `[[link]]` you write between two pages is an
   edge in the graph. When you mention a thing that has (or should have) its
   own page, link it. The graph is where the value compounds.

## How to compile (the core loop)

When new material appears in `raw/`:

1. Read the raw file end to end.
2. For each concrete thing or idea it discusses, find the matching page in
   `entities/` or `concepts/` (check `INDEX.md`). Create it from the template
   only if none exists.
3. Update that page with what's new. Add a dated bullet under `## Log`, cite
   the raw source, and link related pages.
4. Update `INDEX.md` if you created a page or its one-line description changed.
5. Ship every change as a **diff** you can show — the exact before/after lines
   — never as a bare claim that you "updated" something.

## When answering a question from the vault

Walk the links, don't scan everything. Start from the most relevant page,
follow its `[[links]]` to related pages, and cite every page you drew from by
name. If the answer rests on a single unverified page, say so.

## Cost discipline

Compiling and linting are routine work — run them on a cheap/fast model. Only
the weekly cross-vault **synthesis** pass (see `scripts/`) justifies the
premium model, because it reasons across the whole graph at once. Routing
routine work to the top model is how people burn money for nothing.

## Front-matter contract

Every compiled page starts with YAML front matter:

```yaml
---
type: entity            # or: concept
summary: One line, plain language, what this page is.
tags: [client, active]  # freeform, optional
sources:                # required: at least one link into raw/
  - "[[raw/2026-08-21-example-call]]"
created: 2026-08-21
updated: 2026-08-21
expires: 2027-02-21     # optional: for fast-moving facts (pricing, tactics)
---
```

`expires` is how stale knowledge announces itself. Set it on anything that
rots — pricing, platform tactics, "current best practice." The weekly lint
pass surfaces expired pages for review.
