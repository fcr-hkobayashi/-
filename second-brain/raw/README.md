# raw/ — ground truth, read-only

Everything you capture lands here **untouched**: articles, transcripts, call
notes, competitor pages, exports, saved threads.

- The agent **reads** this folder to compile the wiki. It **never edits or
  deletes** anything here.
- Name files `YYYY-MM-DD-short-slug.md` so they sort chronologically.
- Start from `../templates/raw.md`.
- Compiled insight lives in `../entities/` and `../concepts/` and links back
  here. This folder is the ground truth the wiki is built on — keeping it
  clean and unedited is what stops errors from compounding over time.
