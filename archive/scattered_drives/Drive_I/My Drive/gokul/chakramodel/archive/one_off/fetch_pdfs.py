import os
import json
import subprocess

baselines = {
    "FCBFormer": "2208.08352",
    "ColonFormer": "2203.04771", # Or we can search it
}

# Actually let's search arxiv for all 6 and download if found
papers = ["FCBFormer", "ColonFormer", "SSFormer", "UACANet", "Polyp-PVT", "M2SNet"]
results = []

for p in papers:
    print(f"Searching {p} in ArXiv...")
    cmd = ["uv", "run", "scripts/search_arxiv.py", "--query", f"ti:{p}", "--max_results", "1"]
    try:
        res = subprocess.run(cmd, cwd=r"C:\Users\imgk3\.gemini\config\plugins\science\skills\literature_search_arxiv", capture_output=True, text=True)
        if res.stdout.strip():
            data = json.loads(res.stdout)
            if len(data) > 0:
                arxiv_id = data[0]['id'].split('v')[0]
                print(f"Found {p} with ID {arxiv_id}")
                
                # Download
                pdf_path = rf"m:\chakramodel\{p}.pdf"
                down_cmd = ["uv", "run", "scripts/download_paper.py", "--id", arxiv_id, "--format", "pdf", "--output", pdf_path]
                subprocess.run(down_cmd, cwd=r"C:\Users\imgk3\.gemini\config\plugins\science\skills\literature_search_arxiv")
                print(f"Downloaded {p}.pdf")
            else:
                print(f"Not found in arxiv for {p}")
    except Exception as e:
        print(f"Failed for {p}: {e}")
