import json
import os

def parse_openalex(filepath):
    try:
        with open(filepath, 'r', encoding='utf-16') as f:
            data = json.load(f)
    except:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    
    print(f"\n--- OpenAlex: {os.path.basename(filepath)} ---")
    results = data.get('results', [])
    for res in results[:3]:
        title = res.get('title') or res.get('display_name')
        year = res.get('publication_year')
        print(f"Title: {title} ({year})")

def parse_arxiv(filepath):
    if not os.path.exists(filepath): return
    try:
        with open(filepath, 'r', encoding='utf-16') as f:
            data = json.load(f)
    except:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to load {filepath}: {e}")
            return
    print(f"\n--- arXiv: {os.path.basename(filepath)} ---")
    for res in data[:3]:
        print(f"Title: {res.get('title')}")

def parse_pubmed(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"\n--- PubMed: {os.path.basename(filepath)} ---")
    for id_ in data:
        print(f"PMID: {id_}")

def parse_epmc(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"\n--- EuropePMC: {os.path.basename(filepath)} ---")
    results = data.get('results', [])
    for res in results[:3]:
        print(f"Title: {res.get('title')} ({res.get('pubYear')})")

for f in ["openalex_cp_polyp.json", "openalex_pranet.json", "openalex_pvt.json", "openalex_sam.json"]:
    parse_openalex(f"m:/chakramodel/{f}")
parse_arxiv("m:/chakramodel/arxiv_cp_polyp.json")
parse_pubmed("m:/chakramodel/pubmed_cp.json")
parse_epmc("m:/chakramodel/epmc_cp_polyp.json")
