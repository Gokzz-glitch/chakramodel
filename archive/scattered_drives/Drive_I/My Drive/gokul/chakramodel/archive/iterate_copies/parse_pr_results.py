import json

def extract_final_papers(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    decoder = json.JSONDecoder()
    pos = 0
    objects = []
    while pos < len(content):
        try:
            obj, end = decoder.raw_decode(content, pos)
            objects.append(obj)
            pos = end
        except Exception:
            pos += 1
    if objects:
        last = objects[-1]
        return last.get('papers', [])
    return []

def print_section(title, filepath):
    print(f"\n{'='*60}")
    print(f"=== {title} ===")
    print('='*60)
    papers = extract_final_papers(filepath)
    for i, p in enumerate(papers, 1):
        pub = p.get('published', '')[:10]
        title_str = p.get('title', 'N/A')
        pid = p.get('id', '')
        pdf = p.get('pdf_url', '')
        summary = p.get('summary', '')[:300].replace('\n', ' ')
        print(f"\n[{i}] [{pub}] {title_str}")
        print(f"    ArXiv: {pid} | {pdf}")
        print(f"    Summary: {summary}...")
    return papers

p1 = print_section("POLYP SEGMENTATION SOTA (ArXiv)", "pr_polyp_sota.json")
p2 = print_section("TOPOLOGICAL LOSS PERSISTENT HOMOLOGY (ArXiv)", "pr_topo_loss.json")
p3 = print_section("ENDOSCOPIC SLAM SPATIAL MEMORY (ArXiv)", "pr_endo_slam.json")
p4 = print_section("CONFORMAL PREDICTION MEDICAL IMAGING (ArXiv)", "pr_conformal.json")

print(f"\n\nTOTAL: polyp={len(p1)}, topo={len(p2)}, slam={len(p3)}, conformal={len(p4)}")
