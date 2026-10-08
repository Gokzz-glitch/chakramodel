import sys
import os
import glob
import json
import nbformat

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

NOTEBOOK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notebooks")
notebooks = sorted(glob.glob(os.path.join(NOTEBOOK_DIR, "Combo*.ipynb")))

print("==================================================================")
print("METADATA & SCHEMA VERIFICATION MATRIX")
print("==================================================================")

for nb_path in notebooks:
    nb_name = os.path.basename(nb_path)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.reads(f.read(), as_version=4)
        
    meta = nb.metadata
    ks = meta.get("kernelspec", {})
    li = meta.get("language_info", {})
    
    print(f"\nNotebook: {nb_name}")
    print(f"  nbformat: v{nb.nbformat}.{nb.nbformat_minor}")
    print(f"  kernelspec: name='{ks.get('name')}', display_name='{ks.get('display_name')}', language='{ks.get('language')}'")
    print(f"  language_info: name='{li.get('name')}', version='{li.get('version')}', file_extension='{li.get('file_extension')}'")
    print(f"  Total cells: {len(nb.cells)}")
    
    cell_ids = []
    for i, c in enumerate(nb.cells):
        cid = c.get("id", f"no_id_{i}")
        cell_ids.append(cid)
        cell_meta = c.get("metadata", {})
        # check if cell_meta is dict
        assert isinstance(cell_meta, dict), f"Cell {i} metadata is not dict"
        
    unique_ids = len(set(cell_ids)) == len(cell_ids)
    print(f"  Cell IDs unique: {unique_ids} ({len(set(cell_ids))} unique IDs out of {len(cell_ids)} cells)")
    print(f"  Sample Cell IDs: {cell_ids[:4]}")
