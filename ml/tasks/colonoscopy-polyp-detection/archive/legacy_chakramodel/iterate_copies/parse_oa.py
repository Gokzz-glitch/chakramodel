import json
import sys

def read_oa(f):
    with open(f, encoding='utf-8-sig') as fp:
        data = json.load(fp)
    return data

files = ['oa_yolo_vit_polyp.json', 'oa_topo_loss.json', 'oa_endo_slam.json', 'oa_polyp_sota.json']
for fn in files:
    try:
        d = read_oa(fn)
        count = d.get("meta", {}).get("count", 0)
        print(f'\n=== {fn} ({count} results) ===')
        results = d.get('results', [])
        for r in results:
            year = r.get("publication_year")
            name = r.get("display_name", "N/A")
            cites = r.get("cited_by_count", 0)
            doi = r.get("doi", "")
            print(f'  [{year}] {name} | cites={cites} | doi={doi}')
    except Exception as e:
        print(f'{fn}: ERROR {e}')
