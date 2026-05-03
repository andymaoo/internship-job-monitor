import json
import os
import pathlib
import requests

from meta_scraper import fetch_meta_internships
from google_scraper import fetch_google_internships

STATE_FILE = pathlib.Path("seen.json")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

# Company registry. Each entry has type in {"greenhouse","lever","ashby","simplify"}.
# Slugs verified by hitting each ATS API directly (see CHANGELOG).
COMPANIES = [
    # --- Greenhouse ---
    {"name": "databricks", "type": "greenhouse", "slug": "databricks"},
    {"name": "stripe",     "type": "greenhouse", "slug": "stripe"},
    {"name": "airbnb",     "type": "greenhouse", "slug": "airbnb"},
    {"name": "figma",      "type": "greenhouse", "slug": "figma"},
    {"name": "anthropic",  "type": "greenhouse", "slug": "anthropic"},
    {"name": "discord",    "type": "greenhouse", "slug": "discord"},
    {"name": "robinhood",  "type": "greenhouse", "slug": "robinhood"},
    {"name": "coinbase",   "type": "greenhouse", "slug": "coinbase"},
    {"name": "reddit",     "type": "greenhouse", "slug": "reddit"},
    {"name": "pinterest",  "type": "greenhouse", "slug": "pinterest"},
    {"name": "cloudflare", "type": "greenhouse", "slug": "cloudflare"},
    {"name": "instacart",  "type": "greenhouse", "slug": "instacart"},
    {"name": "scale",      "type": "greenhouse", "slug": "scaleai"},
    {"name": "twitch",     "type": "greenhouse", "slug": "twitch"},
    {"name": "roblox",     "type": "greenhouse", "slug": "roblox"},
    {"name": "block",      "type": "greenhouse", "slug": "block"},
    {"name": "samsara",    "type": "greenhouse", "slug": "samsara"},
    {"name": "rubrik",     "type": "greenhouse", "slug": "rubrik"},
    {"name": "mongodb",    "type": "greenhouse", "slug": "mongodb"},
    {"name": "lyft",       "type": "greenhouse", "slug": "lyft"},
    {"name": "xai",        "type": "greenhouse", "slug": "xai"},
    {"name": "together",   "type": "greenhouse", "slug": "togetherai"},
    {"name": "neuralink",  "type": "greenhouse", "slug": "neuralink"},
    {"name": "glean",      "type": "greenhouse", "slug": "gleanwork"},
    {"name": "cerebras",   "type": "greenhouse", "slug": "cerebrassystems"},

    # --- Ashby ---
    {"name": "linear",     "type": "ashby", "slug": "linear"},
    {"name": "vercel",     "type": "ashby", "slug": "vercel"},
    {"name": "perplexity", "type": "ashby", "slug": "perplexity"},
    {"name": "cursor",     "type": "ashby", "slug": "cursor"},
    {"name": "openai",     "type": "ashby", "slug": "openai"},
    {"name": "ramp",       "type": "ashby", "slug": "ramp"},
    {"name": "plaid",      "type": "ashby", "slug": "plaid"},
    {"name": "snowflake",  "type": "ashby", "slug": "snowflake"},
    {"name": "notion",     "type": "ashby", "slug": "notion"},
    {"name": "harvey",     "type": "ashby", "slug": "harvey"},
    {"name": "sierra",     "type": "ashby", "slug": "sierra"},
    {"name": "cohere",     "type": "ashby", "slug": "cohere"},
    {"name": "characterai","type": "ashby", "slug": "character"},
    {"name": "elevenlabs", "type": "ashby", "slug": "elevenlabs"},
    {"name": "replit",     "type": "ashby", "slug": "replit"},
    {"name": "runway",     "type": "ashby", "slug": "runway"},
    {"name": "polymarket", "type": "ashby", "slug": "polymarket"},
    {"name": "kalshi",     "type": "ashby", "slug": "kalshi"},
    {"name": "modal",      "type": "ashby", "slug": "modal"},
    {"name": "decagon",    "type": "ashby", "slug": "decagon"},

    # --- Lever ---
    {"name": "netflix",    "type": "lever", "slug": "netflix"},
    {"name": "palantir",   "type": "lever", "slug": "palantir"},
    {"name": "mistral",    "type": "lever", "slug": "mistral"},

    # --- Meta (custom GraphQL via meta_scraper.py) ---
    {"name": "meta",       "type": "meta"},

    # --- Google (custom batchexecute via google_scraper.py) ---
    {"name": "google",     "type": "google"},

    # --- SimplifyJobs (community-maintained feed covering any MSFT+ tier company
    #     whose job board we don't scrape directly. ~1-2h contributor lag, fine
    #     for companies with wide intern-application windows). ---
    {"name": "simplify-bigtech", "type": "simplify",
     "filter_to": [
         # Big tech with painful boards (Apple/Nvidia Workday). Meta and Google
         # have moved to direct scrapers (meta_scraper.py / google_scraper.py)
         # and must NOT appear here or we'd get duplicate notifications.
         "apple", "amazon", "nvidia",
         "tiktok", "bytedance", "netflix",
         # MSFT+ companies without a standard ATS / previously stubbed
         "doordash", "datadog", "rippling",
         # Big tech / high-TC on Workday or custom sites
         "adobe", "salesforce", "servicenow",
         "intel", "amd", "qualcomm",
         "tesla", "uber", "shopify", "spotify", "snap",
         "waymo", "zoox", "cruise", "figure", "anduril",
         "crowdstrike", "palo alto networks",
         "airtable", "duolingo", "riot games", "tenstorrent",
     ]},
]

# Companies to temporarily skip without deleting from COMPANIES.
COMPANIES_DISABLED = set()

INCLUDE_KEYWORDS = [
    "intern", "internship",
    "software engineer", "software engineering",
    "software developer", "software development",
    "data engineer", "data engineering",
    "machine learning", "ml engineer",
    "ai engineer", "artificial intelligence",
    "technical",
    "engineer", "engineering",
    "developer",
]

EXCLUDE_KEYWORDS = [
    "senior", "staff", "principal",
    "director", "manager", "head of",
    "vice president",
]


def matches_keywords(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False
    return any(inc in t for inc in INCLUDE_KEYWORDS)


def scrape_greenhouse(company):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company['slug']}/jobs"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return [
        {
            "id": f"gh-{company['slug']}-{j['id']}",
            "company": company["name"],
            "title": j["title"],
            "url": j["absolute_url"],
        }
        for j in r.json().get("jobs", [])
        if matches_keywords(j["title"])
    ]


def scrape_lever(company):
    url = f"https://api.lever.co/v0/postings/{company['slug']}?mode=json"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return [
        {
            "id": f"lv-{company['slug']}-{j['id']}",
            "company": company["name"],
            "title": j["text"],
            "url": j["hostedUrl"],
        }
        for j in r.json()
        if matches_keywords(j["text"])
    ]


def scrape_ashby(company):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company['slug']}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return [
        {
            "id": f"ab-{company['slug']}-{j['id']}",
            "company": company["name"],
            "title": j["title"],
            "url": j["jobUrl"],
        }
        for j in r.json().get("jobs", [])
        if matches_keywords(j["title"])
    ]


SIMPLIFY_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json"


def scrape_simplify(company):
    r = requests.get(SIMPLIFY_URL, timeout=30)
    r.raise_for_status()
    targets = {c.lower() for c in company.get("filter_to", [])}
    results = []
    for job in r.json():
        if job.get("company_name", "").lower() not in targets:
            continue
        if not job.get("active", True) or not job.get("is_visible", True):
            continue
        if not matches_keywords(job.get("title", "")):
            continue
        results.append({
            "id": f"simplify-{job['id']}",
            "company": job["company_name"],
            "title": job["title"],
            "url": job["url"],
        })
    return results


def scrape_meta(company):
    return [
        {
            "id": f"meta-{j['id']}",
            "company": "meta",
            "title": j["title"],
            "url": j["url"],
        }
        for j in fetch_meta_internships()
        if matches_keywords(j["title"])
    ]


def scrape_google(company):
    return [
        {
            "id": f"google-{j['id']}",
            "company": "google",
            "title": j["title"],
            "url": j["url"],
        }
        for j in fetch_google_internships()
        if matches_keywords(j["title"])
    ]


SCRAPERS = {
    "greenhouse": scrape_greenhouse,
    "lever":      scrape_lever,
    "ashby":      scrape_ashby,
    "simplify":   scrape_simplify,
    "meta":       scrape_meta,
    "google":     scrape_google,
}


def notify(job):
    if not NTFY_TOPIC:
        print(f"[dry-run] would notify: {job['company']} — {job['title']}")
        return
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=f"{job['company'].upper()}: {job['title']}".encode(),
        headers={
            "Title": "New job posted",
            "Priority": "high",
            "Click": job["url"],
            "Tags": "briefcase",
        },
    )


def notify_scraper_error(scraper_name: str, error: str):
    """Surfaces brittle-scraper failures (Google batchexecute, Meta GraphQL, etc.)
    so we know within ~10 min when an upstream API change breaks something —
    instead of silently degrading. Body is truncated to keep ntfy happy."""
    body = f"{scraper_name}: {error}"[:200]
    if not NTFY_TOPIC:
        print(f"[dry-run] would alert: {body}")
        return
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=body.encode(),
        headers={
            "Title": "Scraper broken",
            "Priority": "default",
            "Tags": "warning",
        },
    )


def main():
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        seen_ids = set(state.get("ids", []))
        first_run = bool(state.get("seed_run", False))
    else:
        seen_ids = set()
        first_run = True

    all_jobs = []
    errors: list[tuple[str, str]] = []
    for company in COMPANIES:
        if company["name"] in COMPANIES_DISABLED:
            print(f"{company['name']}: [disabled]")
            continue
        try:
            jobs = SCRAPERS[company["type"]](company)
        except Exception as e:
            print(f"[error] {company['name']}: {e}")
            errors.append((company["name"], str(e)))
            continue
        print(f"{company['name']}: {len(jobs)} matching roles")
        all_jobs.extend(jobs)

    new_jobs = [j for j in all_jobs if j["id"] not in seen_ids]

    if first_run:
        print(f"[first run] found {len(all_jobs)} jobs, not sending notifications")
    else:
        print(f"found {len(new_jobs)} NEW jobs")
        for job in new_jobs:
            print(f"  NEW: {job['company']} — {job['title']}")
            notify(job)
        # Surface scraper failures so brittle endpoints (Google/Meta) don't
        # degrade silently. Off during first_run to avoid baseline-seed noise.
        for scraper_name, err in errors:
            notify_scraper_error(scraper_name, err)

    # Union (not replace): if an ATS briefly returns empty, we don't want the
    # next successful response to re-notify the same IDs. Once seen, always seen.
    all_ids = sorted(seen_ids | {j["id"] for j in all_jobs})
    STATE_FILE.write_text(json.dumps({"ids": all_ids}, indent=2))


if __name__ == "__main__":
    main()
