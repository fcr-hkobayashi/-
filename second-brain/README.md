# Second Brain

A file-based knowledge base an AI agent navigates, compiles, and maintains on
its own — the "second brain" built in Obsidian and run through Claude Code.
Plain markdown on disk: you read it in Obsidian, the agent works the folder
directly. Same model, better outputs, because now it knows your business.

## Structure

```
second-brain/
├── CLAUDE.md        ← the agent's operating manual (read this first)
├── INDEX.md         ← front door: every page in one line
├── raw/             ← captured material, untouched, read-only ground truth
├── entities/        ← one page per concrete thing (client, competitor, tool, person)
├── concepts/        ← one page per idea (strategy, pattern, lesson)
├── synthesis/       ← weekly cross-vault reports the agent writes
├── templates/       ← starting points for raw / entity / concept pages
└── scripts/         ← the maintenance loops that keep it alive
```

Four pieces carry the whole system: `raw/` (ground truth), `entities/` and
`concepts/` (the compiled wiki), and `INDEX.md` (the map). The agent's job is
**compiling** — reading `raw/` and updating the wiki, linking pages as it goes.
Every `[[link]]` is an edge in a graph, which is why the vault gets *stronger*
as it grows instead of noisier.

## Quick start (≈ an hour)

1. **Read `CLAUDE.md`.** It's the contract the agent follows — the four pieces,
   the writing rules, the front-matter format, the cost discipline.
2. **Open this folder in Obsidian** (point Obsidian at `second-brain/` as a
   vault). Turn on the graph view; that's your window into the brain.
3. **Backfill `raw/`** with what you already own — old chat transcripts, saved
   threads, notes exports, client folders, past research. Use
   `templates/raw.md`, name files `YYYY-MM-DD-slug.md`.
4. **Run a compile pass** to turn that raw pile into a linked wiki:
   ```bash
   cd second-brain && ./scripts/nightly-compile.sh
   ```
   (or open Claude Code here and tell it to compile `raw/` per `CLAUDE.md`.)
5. **Wire the loops** so it stays alive without you filing anything — see
   `scripts/README.md` for cron + the session-end hook.

## Keeping it alive

| Loop | Cadence | What it does |
| ---- | ------- | ------------ |
| Session-end hook | every session | mines what just happened into dated notes |
| Nightly compile | nightly | folds new `raw/` into the wiki (cheap model) |
| Weekly lint | weekly | dead links, dupes, contradictions, expiries |
| Weekly synthesis | weekly | reads the whole vault, writes what changed (premium model) |

Only the weekly synthesis uses the premium model; everything else is routine
work on the cheap tier. Details and setup in `scripts/README.md`.

## Working principles

- **Raw is sacred.** The agent never edits or deletes `raw/`. Compiling on top
  of a fixed ground truth is what stops errors from compounding.
- **Every compiled page cites a source** back into `raw/`. No source → it's a
  claim, not knowledge, and gets flagged.
- **Changes ship as diffs**, not as "I updated it." The diff is the proof.
- **Walk the links** to answer questions; don't scan everything.
