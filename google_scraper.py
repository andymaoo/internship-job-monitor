"""
Google Careers job scraper (batchexecute).

Three-step flow:
  1. GET the careers results page to extract session tokens (bl, f.sid, at)
  2. POST to /batchexecute with f.req payload
  3. Parse the chunked )]}' response and extract job data
"""

import json
import re
import requests


CAREERS_URL = "https://www.google.com/about/careers/applications/jobs/results/"
BATCHEXECUTE_URL = (
    "https://www.google.com/about/careers/applications/_"
    "/HiringCportalFrontendUi/data/batchexecute"
)

RPC_ID = "r06xKb"

# Employment type enum (observed: 2 = INTERN). Test others by changing
# filters in the UI and re-capturing the f.req.
EMPLOYMENT_INTERN = 2
EMPLOYMENT_FULLTIME = 1  # GUESS - verify by capturing a full-time search

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)


def get_session_tokens(session: requests.Session, page_url: str) -> dict:
    """Fetch the careers page and extract bl + f.sid tokens.

    Historically also needed an `at` (SNlM0e) auth token, but as of 2026 the
    careers page no longer ships one and batchexecute returns full data without
    it. If Google re-introduces auth on this endpoint, this is where to add it.
    """
    resp = session.get(
        page_url,
        headers={"user-agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    html = resp.text

    bl_match = re.search(r'"cfb2h":"([^"]+)"', html)
    sid_match = re.search(r'"FdrFJe":"(-?\d+)"', html)

    if not bl_match or not sid_match:
        raise RuntimeError(
            f"Token extraction failed. "
            f"bl={bool(bl_match)}, sid={bool(sid_match)}. "
            f"Google may have changed inline state format."
        )

    return {
        "bl": bl_match.group(1),
        "sid": sid_match.group(1),
    }


def build_freq(
    query: str = "",
    employment_types: list[int] | None = None,
    page: int = 1,
) -> str:
    """Build the f.req parameter for batchexecute.

    Schema reverse-engineered from live request:
        [[ query_string, null, null, [employment_type_int], "en", null, null, page_num ]]

    Note the double-wrapping: outer array contains one inner array of args.
    """
    inner_args = [[
        query,
        None,
        None,
        employment_types or [],
        "en",
        None,
        None,
        page,
    ]]
    inner_json = json.dumps(inner_args, separators=(",", ":"))

    # The "3" at the end (vs "generic") is the observed request type marker
    outer = [[[RPC_ID, inner_json, None, "3"]]]
    return json.dumps(outer, separators=(",", ":"))


def parse_batchexecute_response(text: str) -> list:
    """Parse Google's chunked )]}' response format.

    The chunk-length numbers Google emits don't always equal the byte-length
    of the JSON that follows — sometimes they include trailing newline /
    next-chunk-length bytes. So we use JSONDecoder.raw_decode to extract
    valid JSON greedily and skip ahead.

    Returns list of (rpc_id, payload) tuples.
    """
    if text.startswith(")]}'"):
        text = text[4:]
    text = text.lstrip("\n")

    decoder = json.JSONDecoder()
    results = []
    pos = 0
    while pos < len(text):
        # Skip any whitespace / chunk-length-number lines until we hit a JSON-
        # array start; raw_decode only handles JSON values.
        while pos < len(text) and text[pos] != "[":
            pos += 1
        if pos >= len(text):
            break
        try:
            frames, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            break
        pos = end

        if not isinstance(frames, list):
            continue
        for frame in frames:
            if not isinstance(frame, list) or len(frame) < 3:
                continue
            if frame[0] == "wrb.fr" and frame[2]:
                try:
                    payload = json.loads(frame[2])
                    results.append((frame[1], payload))
                except json.JSONDecodeError:
                    pass

    return results


def search_jobs(
    query: str = "",
    employment_types: list[int] | None = None,
    page: int = 1,
):
    """Search Google Careers and return raw RPC payload."""
    session = requests.Session()

    if employment_types == [EMPLOYMENT_INTERN]:
        page_url = f"{CAREERS_URL}?employment_type=INTERN"
    else:
        page_url = CAREERS_URL

    tokens = get_session_tokens(session, page_url)

    freq = build_freq(query=query, employment_types=employment_types, page=page)

    params = {
        "rpcids": RPC_ID,
        "source-path": "/about/careers/applications/jobs/results/",
        "f.sid": tokens["sid"],
        "bl": tokens["bl"],
        "hl": "en",
        "soc-app": "1",
        "soc-platform": "1",
        "soc-device": "2",
        "_reqid": "100000",
        "rt": "c",
    }

    body = {"f.req": freq}

    headers = {
        "user-agent": USER_AGENT,
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        "x-same-domain": "1",
        "origin": "https://www.google.com",
        "referer": "https://www.google.com/",
    }

    resp = session.post(
        BATCHEXECUTE_URL,
        params=params,
        data=body,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()

    parsed = parse_batchexecute_response(resp.text)

    for rpc_id, payload in parsed:
        if rpc_id == RPC_ID:
            return payload

    raise RuntimeError(
        f"No {RPC_ID} frame in response. Raw start: {resp.text[:500]}"
    )


def _safe_get(obj, path):
    """Walk nested indexes safely, returning None on any miss."""
    for p in path:
        try:
            obj = obj[p]
        except (IndexError, KeyError, TypeError):
            return None
    return obj


def extract_jobs(payload) -> list[dict]:
    """Walk the response and pull out job fields.

    SCHEMA WARNING: index paths are reverse-engineered. On first run, keep
    DEBUG_DUMP=True in __main__ and inspect the raw structure to verify
    these paths still match. As of 2026-04: entry[0]=id, [1]=title,
    [2]=apply_url, [3]=[null, description_html], [4]=[null, quals_html],
    [9]=list of [city_name, [addrs], city_short, postal, state, country].
    """
    if not payload or not isinstance(payload, list):
        return []

    job_list = payload[0] if payload else []
    if not isinstance(job_list, list):
        return []

    jobs = []
    for entry in job_list:
        loc_entries = _safe_get(entry, [9]) or []
        # Each loc is [city_name, [addrs], city_short, postal, state, country]
        locations = [
            loc[0] for loc in loc_entries
            if isinstance(loc, list) and loc and isinstance(loc[0], str)
        ]
        jobs.append({
            "id": _safe_get(entry, [0]),
            "title": _safe_get(entry, [1]),
            "url": _safe_get(entry, [2]),
            "locations": locations,
        })

    return jobs


def fetch_google_internships() -> list[dict]:
    """Convenience used by scrape.py: pull current Google intern postings.

    Returns up to ~50 results per page; we paginate until a page is empty
    or returns < page_size results.
    """
    all_jobs = []
    for page in range(1, 11):  # safety cap at 10 pages
        payload = search_jobs(employment_types=[EMPLOYMENT_INTERN], page=page)
        page_jobs = extract_jobs(payload)
        if not page_jobs:
            break
        all_jobs.extend(page_jobs)
        if len(page_jobs) < 20:
            break
    return all_jobs


if __name__ == "__main__":
    jobs = fetch_google_internships()
    print(f"Found {len(jobs)} internships\n")
    for job in jobs[:10]:
        locs = ", ".join(job["locations"][:3])
        print(f"- {job['title']:60} ({locs})")
        print(f"  {job['url'][:100]}")
