import subprocess
import json
import os
import sys

baselines = ["FCBFormer polyp", "ColonFormer polyp", "SSFormer polyp", "UACANet", "CASCADE polyp", "M2SNet polyp"]
results = {}

for baseline in baselines:
    cmd = [
        "uv", "run", "scripts/openalex_cli.py", "filter", "works",
        "--search", f"{baseline} segmentation",
        "--per-page", "2"
    ]
    print(f"Running for {baseline}...")
    try:
        res = subprocess.run(cmd, cwd=r"C:\Users\imgk3\.gemini\config\plugins\science\skills\literature_search_openalex", capture_output=True, text=True, encoding='utf-8')
        if res.returncode == 0:
            data = json.loads(res.stdout)
            results[baseline] = []
            for d in data.get("results", []):
                results[baseline].append({
                    "title": d.get("display_name"),
                    "id": d.get("id"),
                    "doi": d.get("doi"),
                    "year": d.get("publication_year"),
                    "abstract": d.get("abstract")
                })
        else:
            print(f"Error for {baseline}: {res.stderr}")
    except Exception as e:
        print(f"Exception for {baseline}: {e}")

with open(r"m:\chakramodel\sota_results_clean.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("Done. Saved to sota_results_clean.json")
