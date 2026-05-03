"""
Meta Careers job scraper.

Two-step flow:
  1. GET the careers page to extract the `lsd` session token from inline JS
  2. POST to /graphql with doc_id + variables + lsd
Returns parsed JSON of all matching jobs.
"""

import json
import re
import requests


META_GRAPHQL_URL = "https://www.metacareers.com/graphql"
META_JOBS_URL = "https://www.metacareers.com/jobs"

# This rotates occasionally (every few months). When the scraper breaks with
# an empty response or a "doc_id" error, re-capture this from DevTools.
DOC_ID = "29615178951461218"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)


def get_lsd_token(session: requests.Session) -> str:
    """Fetch the careers page and extract the LSD session token from HTML."""
    resp = session.get(
        META_JOBS_URL,
        headers={
            "user-agent": USER_AGENT,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            # Meta's edge returns a generic 400 without these — they're how a
            # real top-level navigation looks vs. a bare programmatic GET.
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        },
        timeout=15,
    )
    resp.raise_for_status()

    # The token appears inline as: ["LSD",[],{"token":"AbC..."},NN]
    match = re.search(r'"LSD",\[\],\{"token":"([^"]+)"\}', resp.text)
    if not match:
        raise RuntimeError("Could not find LSD token in page HTML")
    return match.group(1)


def search_jobs(
    query: str = "",
    roles: list[str] | None = None,
    teams: list[str] | None = None,
    offices: list[str] | None = None,
    divisions: list[str] | None = None,
    sort_by_new: bool = True,
    is_remote_only: bool = False,
) -> dict:
    """Run a job search against Meta Careers GraphQL endpoint.

    Args mirror the search_input variables from the live request.
    Pass empty defaults for filters you don't care about.
    """
    session = requests.Session()
    lsd = get_lsd_token(session)

    variables = {
        "search_input": {
            "q": query,
            "divisions": divisions or [],
            "offices": offices or [],
            "roles": roles or [],
            "leadership_levels": [],
            "saved_jobs": [],
            "saved_searches": [],
            "sub_teams": [],
            "teams": teams or [],
            "is_leadership": False,
            "is_remote_only": is_remote_only,
            "sort_by_new": sort_by_new,
            "results_per_page": None,
        }
    }

    # Minimal payload: only what the server actually validates.
    payload = {
        "lsd": lsd,
        "fb_api_req_friendly_name": "CareersJobSearchResultsDataQuery",
        "fb_api_caller_class": "RelayModern",
        "variables": json.dumps(variables, separators=(",", ":")),
        "doc_id": DOC_ID,
    }

    headers = {
        "user-agent": USER_AGENT,
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "x-fb-lsd": lsd,
        "x-fb-friendly-name": "CareersJobSearchResultsDataQuery",
        "origin": "https://www.metacareers.com",
        "referer": "https://www.metacareers.com/jobs",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

    resp = session.post(
        META_GRAPHQL_URL, data=payload, headers=headers, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def extract_jobs(response: dict) -> list[dict]:
    """Pull the job list out of the raw GraphQL response."""
    try:
        all_jobs = response["data"]["job_search_with_featured_jobs"]["all_jobs"]
    except (KeyError, TypeError):
        # Schema changed or empty response - dump for debugging
        raise RuntimeError(
            f"Unexpected response shape: {json.dumps(response)[:500]}"
        )

    jobs = []
    for j in all_jobs:
        jobs.append(
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "locations": j.get("locations", []),
                "teams": j.get("teams", []),
                "sub_teams": j.get("sub_teams", []),
                "url": f"https://www.metacareers.com/jobs/{j.get('id')}/",
            }
        )
    return jobs


def fetch_meta_internships() -> list[dict]:
    """Convenience used by scrape.py: pull every active Meta internship."""
    return extract_jobs(search_jobs(roles=["Internship"]))


if __name__ == "__main__":
    jobs = fetch_meta_internships()
    print(f"Found {len(jobs)} internships\n")
    for job in jobs[:15]:
        locs = ", ".join(job["locations"][:3])
        print(f"- {job['title']} ({locs})")
        print(f"  {job['url']}")
