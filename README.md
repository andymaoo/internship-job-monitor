# internship-job-monitor

Polls tech internship postings (Greenhouse, Lever, Ashby, Meta GraphQL, Google batchexecute, SimplifyJobs JSON), dedupes with `seen.json`, and sends push alerts via [ntfy.sh](https://ntfy.sh).

## Run locally

```bash
pip install -r requirements.txt
python scrape.py
```

Set `NTFY_TOPIC` to your ntfy topic name (repository secret for Actions). Without it, the scraper prints `[dry-run]` lines only.

## GitHub Actions

1. Push this repo to GitHub (default branch `main`).
2. Repo → **Settings → Secrets and variables → Actions** → add **`NTFY_TOPIC`** (your topic string).
3. Allow Actions to push: **Settings → Actions → General → Workflow permissions** → **Read and write permissions**.

The workflow runs every 10 minutes and commits updates to `seen.json`. Do not commit `seen.json` before the first run: the scraper treats a missing state file as the baseline seed (no notifications); afterward Actions commits `seen.json` for you.
