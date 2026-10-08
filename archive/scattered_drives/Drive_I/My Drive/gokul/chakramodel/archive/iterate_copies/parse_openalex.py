import json

# Try different encodings
for enc in ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-8', 'latin-1']:
    try:
        with open('openalex.json', 'r', encoding=enc) as f:
            d = json.load(f)
        print(f"Successfully read with encoding: {enc}")
        break
    except Exception as e:
        print(f"Failed with {enc}: {e}")
        continue

results = d.get('results', d.get('data', []))
print(f"Total results: {len(results)}")
print()
for i, r in enumerate(results[:40]):
    title = r.get('display_name', r.get('title', ''))[:100]
    year = r.get('publication_year', '')
    cites = r.get('cited_by_count', '')
    doi = r.get('doi', '')
    print(f"{i+1}. [{year}] cites={cites} | {title}")
    if doi:
        print(f"   DOI: {doi}")
