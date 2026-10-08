import json

files = ['openalex_cp_polyp.json', 'openalex_pranet.json', 'openalex_sam.json', 'openalex_pvt.json']
for f in files:
    try:
        with open(f, encoding='utf-16') as file:
            data = json.load(file)
            print(f'\n--- {f} ---')
            for r in data.get('results', []):
                print(f"Title: {r.get('display_name')}")
                print(f"Year: {r.get('publication_year')}")
                print(f"Citations: {r.get('cited_by_count')}")
    except Exception as e:
        print(f'Error reading {f}: {e}')
