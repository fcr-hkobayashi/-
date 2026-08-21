You are the WEEKLY LINT pass for a second-brain vault. This keeps the graph
clean. Routine work — cheap model.

A deterministic report has already been generated (dead links, missing
sources, expired pages, likely duplicate titles). It is pasted below or found
at scripts/.lint-report.txt. Start from it, then use judgment.

Task:
1. Dead links → fix the target, or remove the link if the page is genuinely
   gone.
2. Pages missing a source link back to raw/ → flag them clearly (add a
   `> ⚠️ NO SOURCE` line at the top) rather than silently trusting them.
3. Expired pages (past their `expires:` date) → flag for review; if you can
   confirm they're still current from raw/, bump the date, otherwise leave the
   flag.
4. Duplicate pages covering the same thing → merge into one, keep the richer
   page, update INDEX.md and inbound links, delete the loser.
5. Contradictions between pages → surface them; if raw/ resolves it, fix the
   wrong page (delete-and-correct, per CLAUDE.md).

Rules: never touch raw/. Update INDEX.md to match reality. Show every change
as a diff and end with a short summary of what you fixed vs. flagged.
