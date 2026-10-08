"""
=============================================================
  AGRIMATE - Automated Farming Research Poller
  Polls Semantic Scholar & OpenAlex APIs every 2 minutes
  for new global farming research papers.
  
  Saves findings to:
    - findings.json    (machine-readable, deduplicated)
    - findings.md      (human-readable live report)
  
  Run: python farming_research_poller.py
=============================================================
"""

import os
import json
import time
import hashlib
import schedule
import requests
from datetime import datetime, timezone

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────

OUTPUT_DIR   = os.path.dirname(os.path.abspath(__file__))
JSON_FILE    = os.path.join(OUTPUT_DIR, "findings.json")
MD_FILE      = os.path.join(OUTPUT_DIR, "findings.md")
LOG_FILE     = os.path.join(OUTPUT_DIR, "poller.log")

POLL_INTERVAL_MINUTES = 5   # Increased to 5 mins to stay under rate limits while collecting data
RESULTS_PER_QUERY     = 20  # Increased to 20 to get more "bulk" when we do get through
GLOBAL_429_COOLDOWN   = 60  # Sleep 60s if we hit a hard rate limit

# Search queries — covers all regions and farming categories
SEARCH_QUERIES = [
    "precision agriculture technology crop yield",
    "agroecology sustainable farming Latin America",
    "climate smart agriculture Africa food security",
    "smallholder farming Asia water management",
    "organic farming biodiversity Europe soil health",
    "pastoral farming drought climate Australia",
    "natural farming soil carbon sequestration",
    "livestock greenhouse gas mitigation silvopastoral",
    "drone remote sensing crop disease detection",
    "AI machine learning crop recommendation system",
    "vertical farming urban agriculture food systems",
    "NDVI satellite crop health monitoring",
    "soil microbiome agricultural sustainability",
    "irrigation technology water scarcity agriculture",
    "crop disease pest management global",
]

# ─── COLOUR CODES (ANSI) ───────────────────────────────────────────────────────

GREEN   = "\033[92m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
RED     = "\033[91m"
BOLD    = "\033[1m"
RESET   = "\033[0m"

# ─── UTILITIES ─────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    colour = {"INFO": CYAN, "OK": GREEN, "WARN": YELLOW, "ERR": RED}.get(level, RESET)
    full = f"[{ts}] [{level}] {msg}"
    print(f"{colour}{full}{RESET}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full + "\n")


def paper_id(paper: dict) -> str:
    """Deterministic unique ID for a paper based on title+doi."""
    key = (paper.get("doi") or paper.get("title", "")).lower().strip()
    return hashlib.sha1(key.encode()).hexdigest()


def load_db() -> dict:
    """Load existing findings JSON database."""
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"papers": {}, "meta": {"last_updated": None, "total": 0}}


def save_db(db: dict):
    """Persist findings JSON database."""
    db["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    db["meta"]["total"] = len(db["papers"])
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ─── API FETCHERS ──────────────────────────────────────────────────────────────

def fetch_semantic_scholar(query: str, limit: int = 5, retries: int = 3) -> list:
    """Fetch papers from Semantic Scholar Graph API with exponential backoff."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "paperId,title,year,abstract,authors,venue,externalIds,publicationDate",
    }
    for attempt in range(retries):
        try:
            time.sleep(3.0 * (attempt + 1))  # Increased base sleep to 3s
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                wait = 60 * (attempt + 1) # Much longer wait
                log(f"SemanticScholar rate-limited. Global cooldown {wait}s...", "WARN")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw_papers = resp.json().get("data", [])
            results = []
            for p in raw_papers:
                doi = (p.get("externalIds") or {}).get("DOI", None)
                results.append({
                    "source"    : "SemanticScholar",
                    "title"     : p.get("title", "Untitled"),
                    "year"      : p.get("year"),
                    "abstract"  : (p.get("abstract") or "No abstract available.")[:600],
                    "authors"   : ", ".join([a.get("name", "") for a in (p.get("authors") or [])[:4]]),
                    "venue"     : p.get("venue", "Unknown Journal"),
                    "doi"       : doi,
                    "url"       : f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}",
                    "query"     : query,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
            return results
        except Exception as e:
            log(f"SemanticScholar error [{query[:40]}] attempt {attempt+1}: {e}", "WARN")
    return []


def fetch_openalex(query: str, limit: int = 5) -> list:
    """Fetch papers from OpenAlex API (fully free, no API key required)."""
    url = "https://api.openalex.org/works"
    params = {
        "search"   : query,
        "per-page" : limit,
        "filter"   : "type:article",
        "sort"     : "publication_date:desc",
        "select"   : "id,display_name,publication_year,abstract_inverted_index,authorships,primary_location,doi",
    }
    try:
        headers = {"User-Agent": "AgriFarmingResearchPoller/1.0 (mailto:agri@research.io)"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        raw_papers = resp.json().get("results", [])
        results = []
        for p in raw_papers:
            # Reconstruct abstract from inverted index
            inv = p.get("abstract_inverted_index") or {}
            abstract = _reconstruct_abstract(inv)
            authors = ", ".join([
                a.get("author", {}).get("display_name", "")
                for a in (p.get("authorships") or [])[:4]
            ])
            location = p.get("primary_location") or {}
            venue = (location.get("source") or {}).get("display_name", "Unknown Journal")
            doi = p.get("doi", "")
            results.append({
                "source"    : "OpenAlex",
                "title"     : p.get("display_name", "Untitled"),
                "year"      : p.get("publication_year"),
                "abstract"  : abstract[:600],
                "authors"   : authors,
                "venue"     : venue,
                "doi"       : doi,
                "url"       : doi if doi else p.get("id", ""),
                "query"     : query,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
        return results
    except Exception as e:
        log(f"OpenAlex error [{query[:40]}]: {e}", "WARN")
        return []


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract text from OpenAlex's inverted index format."""
    if not inverted_index:
        return "No abstract available."
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words.keys()))


# ─── MARKDOWN REPORT GENERATOR ─────────────────────────────────────────────────

def generate_markdown(db: dict):
    """Generate a human-readable Markdown report from the findings database."""
    papers = list(db["papers"].values())
    papers.sort(key=lambda p: (p.get("year") or 0), reverse=True)

    total     = len(papers)
    updated   = db["meta"].get("last_updated", "N/A")

    lines = [
        "# 🌾 AGRIMATE — Live Farming Research Findings",
        f"\n> **Last Updated:** `{updated}`  |  **Total Papers:** `{total}`\n",
        "---\n",
    ]

    # Group by year
    by_year: dict = {}
    for p in papers:
        yr = str(p.get("year") or "Unknown Year")
        by_year.setdefault(yr, []).append(p)

    for yr in sorted(by_year.keys(), reverse=True):
        lines.append(f"\n## 📅 {yr}\n")
        for p in by_year[yr]:
            title   = p.get("title", "Untitled")
            authors = p.get("authors", "Unknown")
            venue   = p.get("venue", "Unknown Journal")
            source  = p.get("source", "")
            url     = p.get("url", "")
            abstract= p.get("abstract", "")
            query   = p.get("query", "")
            fetched = p.get("fetched_at", "")[:10]

            lines.append(f"### 📄 {title}")
            lines.append(f"- **Authors:** {authors}")
            lines.append(f"- **Year:** {yr}  |  **Venue:** {venue}  |  **Source:** `{source}`")
            lines.append(f"- **Search Query:** `{query}`")
            lines.append(f"- **Fetched:** {fetched}")
            if url:
                lines.append(f"- **Link:** [{url}]({url})")
            lines.append(f"\n> {abstract}\n")
            lines.append("---\n")

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log(f"Markdown report updated → {MD_FILE}", "OK")


# ─── MAIN POLLING CYCLE ────────────────────────────────────────────────────────

cycle_count = [0]

def run_poll():
    """Core polling function — called every POLL_INTERVAL_MINUTES."""
    cycle_count[0] += 1
    log(f"{BOLD}--- Poll Cycle #{cycle_count[0]} Starting ---{RESET}", "INFO")

    db = load_db()
    new_count = 0

    for query in SEARCH_QUERIES:
        # Alternate between SS and OpenAlex to avoid rate limits
        fetchers = [fetch_semantic_scholar, fetch_openalex]
        for fetcher in fetchers:
            papers = fetcher(query, limit=RESULTS_PER_QUERY)
            for paper in papers:
                pid = paper_id(paper)
                if pid not in db["papers"]:
                    db["papers"][pid] = paper
                    new_count += 1
                    log(f"  + NEW: [{paper['year']}] {paper['title'][:70]}...", "OK")
            time.sleep(3.0)  # Increased inter-query sleep to 3s to stay under the radar

    save_db(db)
    generate_markdown(db)

    log(
        f"Cycle #{cycle_count[0]} complete | "
        f"New papers this cycle: {new_count} | "
        f"Total in DB: {len(db['papers'])}",
        "OK"
    )
    print()


# ─── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{BOLD}{GREEN}")
    print("+--------------------------------------------------------------+")
    print("|       AGRIMATE - Farming Research Auto-Poller v1.0           |")
    print("+--------------------------------------------------------------+")
    print(f"|  Poll Interval  : Every {POLL_INTERVAL_MINUTES} minutes                             |")
    print(f"|  Queries/Cycle  : {len(SEARCH_QUERIES)} topic queries                          |")
    print(f"|  APIs           : Semantic Scholar + OpenAlex (both FREE)   |")
    print(f"|  Output         : findings.json + findings.md               |")
    print("+--------------------------------------------------------------+")
    print(f"{RESET}\n")

    log("Poller initialised. Running first poll immediately...", "INFO")
    run_poll()  # Run immediately on start

    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(run_poll)
    log(f"Scheduler active — polling every {POLL_INTERVAL_MINUTES} minutes. Press Ctrl+C to stop.", "INFO")

    try:
        while True:
            try:
                schedule.run_pending()
                time.sleep(10)
            except Exception as e:
                log(f"Unexpected error in polling loop: {e}", "ERR")
                time.sleep(10)
    except KeyboardInterrupt:
        log("Poller stopped by user. Goodbye!", "WARN")
        print(f"\n{YELLOW}Poller stopped. Your findings are saved in:{RESET}")
        print(f"  📄 JSON : {JSON_FILE}")
        print(f"  📝 MD   : {MD_FILE}")
        print(f"  📋 LOG  : {LOG_FILE}\n")
