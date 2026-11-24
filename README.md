# Job Radar: Regina · Toronto · Alberta

A daily job hunt for UX / AI-product / accessibility / design roles in three regions, plus a live trends page and intelligence report.

- **`index.html`**: the report page (ledger, trends, intelligence report, opportunities). It reads `data/jobs.json` every time it loads.
- **`data/jobs.json`**: the only file that changes daily. Every job ever seen, with `first_seen`, `last_seen` and `times_seen`, plus one summary per daily run, market signals, opportunities and the intelligence report text.
- **`scripts/merge.py`**: merges a day's scan into `data/jobs.json` (dedupe, first/last seen, ageing, urgent flags, size policy).

## Make it live

Settings → Pages → *Deploy from a branch* → `main` / `(root)`. The page will be at `https://akane-asahi.github.io/job/`.
GitHub Pages on a **private** repo needs a paid plan, and the site is public even when the repo is private. Check you're comfortable with the content being public first.
To view it locally: `python3 -m http.server` in this folder, then open http://localhost:8000. Opening the file directly won't load the JSON.

## Categories

| key | meaning |
|---|---|
| `most_matched` | match score ≥ 78, realistically winnable |
| `urgent_apply` | closes within 10 days, an internship term starting soon, or a fast-moving high-fit role |
| `student_track` | workable while studying full-time (part-time, casual, flexible contract, co-op/internship, on-campus) |
| `ai_frontier` | designs, evaluates or builds AI products |
| `remote_canada` | can be done from Regina |
| `grad_2027_pipeline` | recurring program or cohort to target for a Dec 2027 / Jan 2028 start |
| `watchlist` | strong-fit employer, or a closed/blocked post; watch for the next one |

## Daily run (what the scheduled task does)

1. Clone this repo; read `data/jobs.json` (`meta` holds the profile, scoring and dedupe rules).
2. Search each region (Regina incl. Saskatoon/SK-remote; Toronto/GTA; Calgary + Edmonton) for: UX/UI/product designer, AI product designer / UX for AI, UX researcher, accessibility specialist, service designer, conversational/AI trainer design roles, graphic/print, AI developer. Check employer boards for the tracked employers too.
3. Write today's finds to a temp `candidates.json` (schema in `scripts/merge.py`) with a match score, role family and categories, then run
   `python3 scripts/merge.py candidates.json --date YYYY-MM-DD --notes "..." --coverage coverage.json`.
4. Re-list jobs already on the radar that are still posted, so they get a new `last_seen`.
5. Mondays: refresh `intel` (and `market_signals` / `opportunities` if anything changed) inside `data/jobs.json`.
6. Commit only `data/jobs.json` (and `data/archive/*` if the size policy moved anything) and push to `main`.

When `data/jobs.json` passes ~1.5 MB or 2,500 jobs, closed jobs not seen for 120+ days move to `data/archive/jobs-<year>.json`.
