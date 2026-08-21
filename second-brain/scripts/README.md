# scripts/ — keeping the brain alive

A second brain that only grows when you remember to feed it is dead in three
weeks. These loops run on schedules, not on memory. Each one drives a headless
Claude Code pass (`claude -p`) over the vault with a fixed prompt from
`prompts/`.

| Loop | Script | When | Model | Job |
| ---- | ------ | ---- | ----- | --- |
| Session-end | `session-end-hook.sh` | on every session end (hook) | cheap | mine the transcript for decisions/mistakes/patterns → dated notes |
| Nightly compile | `nightly-compile.sh` | nightly (cron) | cheap | fold new `raw/` material into entity/concept pages |
| Weekly lint | `weekly-lint.sh` | weekly (cron) | cheap | dead links, dupes, contradictions, expiries |
| Weekly synthesis | `weekly-synthesis.sh` | weekly (cron) | **premium** | read across the whole vault → `synthesis/` report |

Only synthesis uses the premium model. Everything else is routine work on the
cheap tier — that split is the whole cost story.

## Prerequisites

- **Claude Code CLI** on PATH (`claude`). Override with `SB_CLAUDE_BIN`.
- **Python 3** for `lint.py` (standard library only).

## Configuration (env vars)

| Var | Default | Meaning |
| --- | ------- | ------- |
| `SB_CHEAP_MODEL` | `claude-haiku-4-5-20251001` | model for compile / lint / session-end |
| `SB_BIG_MODEL`   | `claude-opus-4-8`           | model for weekly synthesis |
| `SB_CLAUDE_BIN`  | `claude`                    | Claude Code binary |
| `SB_DRY_RUN`     | `0`                         | `1` prints the command + prompt instead of running |

Verify wiring without spending anything:

```bash
SB_DRY_RUN=1 ./nightly-compile.sh
```

## Set up the schedules

1. **Cron** — copy `crontab.example`, replace `/ABS/PATH`, then `crontab crontab.example`.
2. **Session-end hook** — merge `settings.hook.json` into your Claude Code
   `settings.json` (in `.claude/` here, or `~/.claude/`), replacing
   `ABSOLUTE_PATH`. The hook backgrounds the miner so ending a session stays
   instant, and guards against triggering itself (`SB_IN_HOOK`).

## The deterministic linter

`lint.py` runs with no model and reports what a script can know for sure —
dead `[[wikilinks]]`, compiled pages missing a `raw/` source, pages past their
`expires:` date, and duplicate titles. `weekly-lint.sh` runs it first and feeds
the report into the model pass, so the model starts from facts. Run it anytime:

```bash
python3 lint.py        # prints a report, also writes .lint-report.txt
```

## A note on the passes committing changes

These scripts edit files in place; they don't commit. If your vault is a git
repo, add `&& git -C "$vault" add -A && git -C "$vault" commit -m 'auto:
<loop>'` to a wrapper, or run a separate commit cron — kept out of here so the
loops stay about knowledge, not git policy.
