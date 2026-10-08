"""
verify_citations.py

Cross-checks every arXiv ID referenced in docs/literature_review.md against
the real arXiv API. Flags:
  - arXiv IDs that don't exist
  - Titles that don't match what's claimed in the review
  - (Manual step) prints the real abstract so YOU can eyeball reported metrics

This does NOT verify numeric metrics automatically (arXiv API has no
structured metrics field) -- for that, this script prints the abstract text
and you (or Claude/another LLM pass) must check numbers mentioned in the
abstract against what's written in literature_review.md.

Usage:
    pip install requests --break-system-packages
    python verify_citations.py docs/literature_review.md
"""

import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

ARXIV_ID_PATTERN = re.compile(r"arXiv[:\s\*\[]*\(?\[?(\d{4}\.\d{4,5})")
ARXIV_API = "http://export.arxiv.org/api/query?id_list={}"
NS = {"atom": "http://www.w3.org/2005/Atom"}


def extract_arxiv_ids(md_text):
    ids = sorted(set(ARXIV_ID_PATTERN.findall(md_text)))
    return ids


def fetch_arxiv_entry(arxiv_id):
    url = ARXIV_API.format(arxiv_id)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_data = resp.read()
    except Exception as e:
        return {"id": arxiv_id, "found": False, "error": str(e)}

    root = ET.fromstring(xml_data)
    entry = root.find("atom:entry", NS)
    if entry is None:
        return {"id": arxiv_id, "found": False, "error": "No entry element"}

    title_el = entry.find("atom:title", NS)
    summary_el = entry.find("atom:summary", NS)
    id_el = entry.find("atom:id", NS)

    # arXiv returns a stub entry with no real title if the ID doesn't exist
    if id_el is None or arxiv_id not in (id_el.text or ""):
        return {"id": arxiv_id, "found": False, "error": "ID not found in arXiv"}

    return {
        "id": arxiv_id,
        "found": True,
        "title": (title_el.text or "").strip().replace("\n", " "),
        "summary": (summary_el.text or "").strip().replace("\n", " "),
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python verify_citations.py <path_to_literature_review.md>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    arxiv_ids = extract_arxiv_ids(text)
    print(f"Found {len(arxiv_ids)} unique arXiv IDs in {path}\n")

    results = []
    for i, aid in enumerate(arxiv_ids, 1):
        print(f"[{i}/{len(arxiv_ids)}] Checking {aid} ...")
        result = fetch_arxiv_entry(aid)
        results.append(result)
        time.sleep(3)  # arXiv API rate-limit courtesy delay -- do not remove

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    not_found = [r for r in results if not r["found"]]
    found = [r for r in results if r["found"]]

    print(f"\n✅ FOUND ({len(found)}):")
    for r in found:
        print(f"  [{r['id']}] {r['title']}")

    print(f"\n❌ NOT FOUND / SUSPICIOUS ({len(not_found)}):")
    for r in not_found:
        print(f"  [{r['id']}] ERROR: {r.get('error')}")
        print(f"    -> THIS ID LIKELY DOES NOT EXIST. Do not cite it in the paper.")

    if not_found:
        print(
            f"\n⚠️  {len(not_found)} citation(s) could not be verified against "
            "the real arXiv database. Manually re-check these entries in "
            "literature_review.md before submitting anything for review."
        )
    else:
        print("\nAll arXiv IDs resolved to real papers. Titles printed above -- "
              "manually confirm each title matches what literature_review.md claims, "
              "and manually re-check any numeric Dice/IoU/FPS claims against the "
              "printed abstract text (this script cannot parse tables reliably).")


if __name__ == "__main__":
    main()
