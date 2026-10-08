import json
import sys

def summarize_json(filepath):
    print(f"--- {filepath} ---")
    with open(filepath, 'r', encoding='utf-16') as f:
        data = json.load(f)
        
    results = data.get('results', [])
    for res in results[:5]:
        title = res.get('title') or res.get('display_name')
        year = res.get('publication_year')
        abstract = res.get('abstract_inverted_index') or {}
        abstract_words = sorted([(int(idx), word) for word, indices in abstract.items() for idx in indices])
        abstract_text = ' '.join([w for i, w in abstract_words])
        print(f"Title: {title} ({year})")
        print(f"Abstract snippet: {abstract_text[:500]}...")
        print("")

for file in ["openalex_cp_polyp.json", "openalex_pranet.json", "openalex_sam.json", "openalex_pvt.json"]:
    summarize_json(f"m:/chakramodel/{file}")
