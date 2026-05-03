# Changelog

## 2026-04-23

### Task 1 — Reset seen.json
- Verified `seen.json` is absent from both local and `origin/main`. No action needed; first-run guard in `main()` will create a fresh baseline on the next Actions run without firing notifications.

### Task 2 — Keyword filter rewrite
- Replaced narrow `KEYWORDS = ["software engineer", "swe", "software development"]` with a broad `INCLUDE_KEYWORDS` set covering intern/early-career SWE, data, ML/AI, and generic "engineer"/"developer"/"technical".
- Added `EXCLUDE_KEYWORDS` (senior/staff/principal/director/manager/head of/vice president) so senior roles don't leak through the broad includes.
- `matches_keywords` now: excludes first, then includes. Case-insensitive substring match (no word boundaries — simple + catches most variants).

### Task 4 — Multi-ATS refactor
- Each company now has a `type` (`greenhouse` | `lever` | `ashby` | `custom`). `SCRAPERS` dict dispatches to `scrape_greenhouse` / `scrape_lever` / `scrape_ashby`.
- `custom` entries reference a function name via `"fn"`, resolved through `globals()`. Stubs return `[]` for now (doordash, datadog, rippling, google, meta, apple, amazon, nvidia).
- Per-company failures are caught in `main()` — one broken slug no longer kills the whole run.
- ID prefix convention: `gh-` / `lv-` / `ab-` (plus future custom prefixes per scraper).
- `notify()` and workflow yml untouched per brief.

### Task 3 — Expanded company list
- Greenhouse additions (verified 200 + non-zero job count): cloudflare, affirm, brex, instacart, chime, scaleai, asana, twitch.
- Slug corrections — these were Greenhouse in the prior list but actually 404 there; moved to Ashby (verified): **ramp, plaid, snowflake, notion**. The old list was silently dropping these via the try/except.
- Ashby additions: linear, vercel, perplexity, cursor, openai.
- Lever additions: netflix, palantir.
- Custom stubs: doordash, datadog, rippling (Workday-based; no standard API), plus google/meta/apple/amazon/nvidia per brief.
- Microsoft intentionally skipped (offer already in hand).
- Quant shops (jane street, citadel, etc.) deferred to a later phase per brief.
- `COMPANIES_DISABLED = set()` added so a company can be muted without deletion.

## 2026-04-23 (second batch)

### Expanded company list — round 2
Added 29 verified companies (all hit via live API calls, non-zero match counts confirmed locally):

- **Greenhouse (+19):** roblox, block (Square/Cash App), gemini, sofi, marqeta, samsara, rubrik, mongodb, elastic, gitlab, dropbox, lyft, xai, together (togetherai), spacex, neuralink, cockroachdb (cockroachlabs), ridgeline, squarespace.
- **Ashby (+9):** harvey, sierra, cohere, characterai, elevenlabs, replit, runway, polymarket, kalshi.
- **Lever (+1):** mistral.

Local test: 2758 matching roles across 59 companies, 0 errors. SpaceX alone contributes 815 (giant engineering org; expected).

### Task 5a — SimplifyJobs community feed
- New scraper type `simplify` reads https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json (~20k records, ~15MB per fetch).
- One `simplify-bigtech` entry filters the feed to big tech whose own boards are too painful to scrape directly (Google batchexecute, Meta GraphQL, Apple/Nvidia Workday, TikTok/ByteDance). Amazon included here since we're not building a direct scraper for now.
- Each record honored for `active` + `is_visible`, then put through the same `matches_keywords()` filter as other sources.
- ID prefix `simplify-<uuid>`.
- Dropped the now-redundant `scrape_google` / `scrape_meta` / `scrape_apple` / `scrape_amazon` / `scrape_nvidia` stubs and their COMPANIES entries.
- Local test: simplify-bigtech contributes 215 matches (TikTok 128, ByteDance 32, Meta 21, NVIDIA 12, Netflix 8, Amazon 8, Apple 6, Google 0). Notification latency for these companies now ~1-2h (Simplify contributor lag) + ~10min (our cron) = tolerable for FAANG-class postings with wide windows.

### Expanded simplify-bigtech filter_to (MSFT+ tier)
- Added 25 more target companies to the Simplify filter, covering any MSFT-or-better company we don't already scrape directly.
- Rolled doordash/datadog/rippling into Simplify coverage — dropped their individual custom stubs and the `scrape_doordash/datadog/rippling` functions. Also removed the now-unused `custom` type branch in `main()`.
- New filter_to list (33 companies): google, meta, apple, amazon, nvidia, tiktok, bytedance, netflix; doordash, datadog, rippling; adobe, salesforce, servicenow; intel, amd, qualcomm; tesla, uber, shopify, spotify, snap; waymo, zoox, cruise, figure, anduril; crowdstrike, palo alto networks; airtable, duolingo, riot games, tenstorrent.
- Many currently 0 active (off-season, April 2026); wired in now so they auto-cover when summer-2027 postings open ~July 2026. Local test: simplify-bigtech 273 matches. Total 3025 across all sources.

### Bugfix — seen.json phantom re-notifications
- `main()` was replacing `seen.json` with only currently-visible IDs each run. When an ATS briefly returned empty (e.g. OpenAI Ashby flaked for one run, returning 0 of ~318 jobs), those IDs dropped from `seen.json`. On the next successful run, all ~313 IDs came back and were re-notified as "new" — a 313-notification storm for jobs that had been visible from the baseline.
- Fixed by unioning old `seen_ids` with currently-visible IDs before writing: `all_ids = sorted(seen_ids | {j['id'] for j in all_jobs})`. Once an ID is seen, it stays. `seen.json` grows linearly (~100KB/month at current rate), manageable for months before any expiry is needed.

### Trim COMPANIES list to MSFT-or-better tier
- User feedback: too many lower-tier postings were leaking through. Cut 15 Greenhouse entries to enforce a Microsoft-or-better bar.
- Specific removes per user request: spacex (volume), cockroachdb, ridgeline, squarespace.
- Smaller-tier fintechs cut: mercury, affirm, brex, chime, gemini, sofi, marqeta. (Bar set by stripe / plaid / robinhood / coinbase / block, which stay.)
- Sub-MSFT SaaS/devtools cut: asana, elastic, gitlab, dropbox.
- Ashby and Lever entries left untouched — already MSFT-or-better.
- simplify-bigtech filter_to left untouched — covers FAANG-tier through that source already.
- Local test: 2054 matches across 45 entries (down from 3025 across 60). Keyword filter unchanged per user's recall-over-precision preference.

### Added 4 hot AI/devtools companies
- Greenhouse: glean (slug `gleanwork`, 39 matches), cerebras (slug `cerebrassystems`, 36 matches).
- Ashby: modal (9 matches), decagon (101 jobs but only 7 match keywords; mostly customer-success/sales roles).
- Brainstormed candidates that don't expose a standard ATS API and aren't in SimplifyJobs either — would each need a custom scraper, so deferred: hugging face, codeium, groq, magic.dev, sourcegraph. User to handle these via native LinkedIn / careers-page alerts.
- Local test: 2145 matches across 49 entries.

### Direct Meta scraper (replaces Simplify's Meta coverage)
- Added `meta_scraper.py` (custom GraphQL flow: GET careers page → extract LSD token → POST to /graphql with doc_id). Patched by adding required `sec-fetch-*` headers to both GET and POST (without them Meta's edge returns a generic 400). Also corrected response-shape parsing — actual key is `job_search_with_featured_jobs.all_jobs`, not `job_search`.
- New `fetch_meta_internships()` helper used by scrape.py.
- New scraper type `meta` registered in SCRAPERS dict, plus a `{"name": "meta", "type": "meta"}` entry in COMPANIES.
- Removed `"meta"` from `simplify-bigtech.filter_to` to prevent duplicate notifications (different IDs from each source for the same job).
- Local test: meta = 20 matches (all PhD Research Scientist internships — fully expected for late-April off-season; SWE intern reqs typically open July).
- Brittleness note: Meta's `DOC_ID` is hardcoded and rotates every few months. When the scraper starts returning empty / "doc_id" errors, recapture from DevTools Network tab on metacareers.com/jobs (look for the CareersJobSearchResultsDataQuery POST).

### Direct Google scraper (replaces Simplify's Google coverage)
- Added `google_scraper.py` (custom batchexecute RPC: GET careers page → extract `bl` + `f.sid` tokens → POST to /batchexecute with f.req payload). Three fixes from the original draft:
  - Removed `at` (SNlM0e) token requirement — Google no longer ships it on the unauthenticated careers page, and batchexecute returns full data without it.
  - Replaced manual chunk-length parsing with `json.JSONDecoder.raw_decode()`, because Google's emitted chunk lengths now include trailing newlines / next-chunk-prefix bytes that confuse `json.loads`.
  - Corrected the schema indices in `extract_jobs` — entry[3] is HTML description, not locations; locations live at entry[9].
- New `fetch_google_internships()` paginates up to 10 pages.
- Removed `"google"` from `simplify-bigtech.filter_to`.
- Local test: google = 6 matches (out of 17 total internships; the 11 filtered out are mostly "Student Researcher" titles that don't trigger any INCLUDE keyword).
- Brittleness note: `RPC_ID = "r06xKb"` and the regex var names (`cfb2h`, `FdrFJe`) all rotate when Google updates their JS bundle. When that happens, the scraper raises and the new alert path (below) fires a ntfy notification.

### Scraper-failure alerting via ntfy
- New `notify_scraper_error(scraper_name, error)` fires a `default`-priority ntfy notification with title "Scraper broken" when any scraper in `main()` raises. Body is `<scraper>: <error>`, truncated to 200 chars.
- `main()` now collects per-company errors during the loop and (only after the first-run guard) emits one ntfy alert per failed scraper per run. Important for the brittle Google/Meta paths where upstream API changes would otherwise degrade silently.
- Deliberately did NOT add a "0-results floor check" alongside this — transient ATS hiccups returning empty are common, and we already neutralized them via the `seen.json` union fix; a floor check would re-introduce false-positive alerts.
