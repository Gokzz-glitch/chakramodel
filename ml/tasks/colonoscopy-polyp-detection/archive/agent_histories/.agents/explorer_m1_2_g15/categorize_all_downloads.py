import json
import re
from pathlib import Path
from collections import defaultdict

def categorize():
    with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\j_downloads_raw.json", "r", encoding="utf-8") as f:
        j_items = json.load(f)
    with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\c_downloads_raw.json", "r", encoding="utf-8") as f:
        c_items = json.load(f)

    all_items = [("C", it) for it in c_items] + [("J", it) for it in j_items]

    # Unrelated/personal filters:
    # 1. Personal docs: passport, resume, receipt, payment, bill, mess fees, profile, invite, ticket
    # 2. Leads: researcher_leads, corporate_leads, russia_moscow_leads, priority_*
    # 3. System/installers: .exe, .msi, eclipse, acer, desktop.ini
    personal_patterns = [
        re.compile(r"passport", re.I),
        re.compile(r"resume", re.I),
        re.compile(r"receipt", re.I),
        re.compile(r"payment", re.I),
        re.compile(r"booking", re.I),
        re.compile(r"mess\s*fees", re.I),
        re.compile(r"bill", re.I),
        re.compile(r"profile\.pdf", re.I),
        re.compile(r"\.ics$", re.I),
        re.compile(r"leads", re.I),
        re.compile(r"eclipse", re.I),
        re.compile(r"acer\s*care", re.I),
        re.compile(r"chatgpt\s*installer", re.I),
        re.compile(r"chromesetup", re.I),
        re.compile(r"desktop\.ini$", re.I),
        re.compile(r"screenshot", re.I),
        re.compile(r"opus_keyword", re.I),
    ]

    # Chakramodel keywords
    chakra_keywords = [
        "chakra", "polyp", "kvasir", "cvc", "etis", "pranet", "colondb",
        "bytetrack", "sam2", "conformal", "anti_fabrication", "combocld",
        "om-krish", "om-final", "finalmuruga", "crossvali", "cross_dataset",
        "v7verifiactiob", "claudev7", "yolo", "combo", "fcbformer", "endoslam"
    ]

    categorized = defaultdict(list)

    for src, item in all_items:
        if item.get("type") != "file":
            continue
        p = item.get("path", "")
        name = item.get("name", Path(p).name)
        size = item.get("size", 0)
        ext = Path(name).suffix.lower()

        is_personal = any(pat.search(name) or pat.search(p) for pat in personal_patterns)
        
        is_chakra = False
        name_lower = name.lower()
        path_lower = p.lower()
        if any(kw in name_lower or kw in path_lower for kw in chakra_keywords):
            is_chakra = True
        if "chakramodel_om_4" in path_lower:
            is_chakra = True

        if is_personal and not ("chakra" in name_lower and ext in ('.pth', '.pt', '.ipynb', '.py', '.json')):
            categorized["unrelated_or_personal"].append((src, p, size))
            continue

        if ext in ('.pth', '.pt', '.onnx', '.ckpt', '.bin', '.h5', '.weights'):
            categorized["weights"].append((src, p, size))
        elif ext == '.zip':
            if is_chakra:
                categorized["chakra_zips"].append((src, p, size))
            else:
                categorized["other_zips"].append((src, p, size))
        elif ext == '.ipynb':
            if is_chakra:
                categorized["chakra_notebooks"].append((src, p, size))
            else:
                categorized["other_notebooks"].append((src, p, size))
        elif ext == '.json':
            if is_chakra:
                categorized["chakra_json"].append((src, p, size))
            else:
                categorized["other_json"].append((src, p, size))
        elif ext == '.py':
            if is_chakra:
                categorized["chakra_py"].append((src, p, size))
            else:
                categorized["other_py"].append((src, p, size))
        elif ext in ('.md', '.txt'):
            if is_chakra:
                categorized["chakra_docs"].append((src, p, size))
            else:
                categorized["other_docs"].append((src, p, size))
        elif ext == '.pdf':
            if is_chakra:
                categorized["chakra_pdf"].append((src, p, size))
            else:
                categorized["other_pdf"].append((src, p, size))
        elif ext in ('.csv', '.tsv'):
            if is_chakra:
                categorized["chakra_csv"].append((src, p, size))
            else:
                categorized["other_csv"].append((src, p, size))
        else:
            if is_chakra:
                categorized["chakra_other"].append((src, p, size))
            else:
                categorized["other"].append((src, p, size))

    print("Summary of categorization:")
    for cat, lst in sorted(categorized.items()):
        print(f"  {cat:25}: {len(lst)} files")

    with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\categorized_inventory.json", "w", encoding="utf-8") as f:
        json.dump({k: [{"src": x[0], "path": x[1], "size": x[2]} for x in v] for k, v in categorized.items()}, f, indent=2)

if __name__ == "__main__":
    categorize()
