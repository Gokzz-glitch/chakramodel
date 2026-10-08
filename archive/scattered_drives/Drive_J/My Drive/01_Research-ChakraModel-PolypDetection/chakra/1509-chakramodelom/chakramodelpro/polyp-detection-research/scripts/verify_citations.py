import sys
import re
import urllib.request
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET
from pathlib import Path
import time
import json

def fetch_arxiv_data(arxiv_id):
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    req = urllib.request.Request(url, headers={'User-Agent': 'PolypResearchBot/1.0 (contact@example.com)'})
    
    max_retries = 3
    retry_delays = [30, 60, 120]
    
    for attempt in range(max_retries + 1):
        try:
            response = urllib.request.urlopen(req)
            data = response.read()
            root = ET.fromstring(data)
            
            entry = root.find('{http://www.w3.org/2005/Atom}entry')
            if entry is None:
                return None
            
            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
            summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
            
            if title_elem is None or summary_elem is None:
                return None
                
            title = title_elem.text.replace('\n', ' ').strip()
            summary = summary_elem.text.replace('\n', ' ').strip()
            
            return {"title": title, "abstract": summary}
            
        except HTTPError as e:
            if e.code in [429, 503]:
                if attempt < max_retries:
                    delay = retry_delays[attempt]
                    print(f"      [Retry] Got HTTP {e.code}. Waiting {delay}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(delay)
                else:
                    return f"Error: HTTP Error {e.code} after {max_retries} retries"
            else:
                return f"Error: HTTP Error {e.code}: {e.reason}"
        except URLError as e:
            # Propagate up so batch logic catches DNS/socket errors
            raise e
        except Exception as e:
            return f"Error: {e}"

def save_checkpoint(checkpoint_path, data, status):
    data['last_status'] = status
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def main():
    target_path = Path("docs/literature_review.md")
    checkpoint_path = Path("docs/verification_checkpoint.json")
    
    if not target_path.exists():
        print(f"Error: {target_path} not found.")
        sys.exit(1)
    if not checkpoint_path.exists():
        print(f"Error: {checkpoint_path} not found.")
        sys.exit(1)
        
    content = target_path.read_text(encoding="utf-8")
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        checkpoint_data = json.load(f)
        
    unverified_papers = checkpoint_data.get("unverified_papers", [])
    if not unverified_papers:
        print("No unverified papers left in checkpoint.")
        sys.exit(0)
    
    paper_pattern = re.compile(r'^####\s*\[(P\d+)\]\s*(.+)$', re.MULTILINE)
    matches = list(paper_pattern.finditer(content))
    arxiv_regex = re.compile(r'(?:arxiv\.org/abs/|arXiv:\s*\[?|arXiv:)(\d{4}\.\d{4,5})', re.IGNORECASE)
    
    papers_to_verify = []
    
    for i, match in enumerate(matches):
        pid = match.group(1)
        if pid not in unverified_papers:
            continue
            
        title_in_doc = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block_text = content[start:end]
        
        arxiv_matches = arxiv_regex.findall(block_text)
        if not arxiv_matches:
            papers_to_verify.append((pid, title_in_doc, None))
        else:
            papers_to_verify.append((pid, title_in_doc, arxiv_matches[0]))

    if not papers_to_verify:
        print("No unverified papers matched in the document.")
        sys.exit(0)

    print("============================================================")
    print("ARXIV CITATION VERIFICATION (BATCHED RESUME)")
    print("============================================================")

    batch_size = 4
    batches = [papers_to_verify[i:i + batch_size] for i in range(0, len(papers_to_verify), batch_size)]
    
    for b_idx, batch in enumerate(batches):
        print(f"\n--- Starting Batch {b_idx + 1}/{len(batches)} (Size: {len(batch)}) ---")
        
        for idx, (pid, title_in_doc, arxiv_id) in enumerate(batch):
            if not arxiv_id:
                print(f"[{pid}] SKIP - No arXiv ID found")
                print(f"Doc Title: {title_in_doc}")
                print("-" * 60)
                checkpoint_data["verified_papers"][pid] = "SKIPPED - No arXiv ID found"
                checkpoint_data["unverified_papers"].remove(pid)
                save_checkpoint(checkpoint_path, checkpoint_data, "Running")
                continue
                
            print(f"[{pid}] Verifying arXiv ID: {arxiv_id}")
            try:
                result = fetch_arxiv_data(arxiv_id)
                
                if result is None:
                    print(f"[{pid}] NOT FOUND")
                    checkpoint_data["verified_papers"][pid] = "NOT FOUND"
                elif isinstance(result, str) and result.startswith("Error"):
                    print(f"[{pid}] COULD NOT VERIFY - {result}")
                    checkpoint_data["verified_papers"][pid] = result
                else:
                    print(f"[{pid}] FOUND")
                    print(f"Doc Title: {title_in_doc}")
                    print(f"Real Title: {result['title']}")
                    # print(f"Abstract: {result['abstract']}") # Suppressed for log clarity
                    checkpoint_data["verified_papers"][pid] = f"FOUND: {result['title']}"
                    
                checkpoint_data["unverified_papers"].remove(pid)
                save_checkpoint(checkpoint_path, checkpoint_data, "Running")
                print("-" * 60)
                
                # Wait 20 seconds between papers, but not after the last paper in the final batch
                if idx < len(batch) - 1 or b_idx < len(batches) - 1:
                    time.sleep(20)
                
            except URLError as e:
                error_msg = f"DNS/Network Error: {e.reason}"
                print(f"      [NETWORK COLLAPSE] {error_msg}")
                print(f"      Stopping verification immediately to save state.")
                save_checkpoint(checkpoint_path, checkpoint_data, f"Paused at {pid} due to {error_msg}")
                sys.exit(1)
            except Exception as e:
                print(f"[{pid}] COULD NOT VERIFY - Exception: {e}")
                print("-" * 60)
                checkpoint_data["verified_papers"][pid] = f"Exception: {e}"
                checkpoint_data["unverified_papers"].remove(pid)
                save_checkpoint(checkpoint_path, checkpoint_data, "Running")
        
        if b_idx < len(batches) - 1:
            print(f"--- Batch {b_idx + 1} Complete. Waiting 3 minutes before next batch ---")
            save_checkpoint(checkpoint_path, checkpoint_data, f"Waiting 3m before Batch {b_idx + 2}")
            time.sleep(180)
            
    save_checkpoint(checkpoint_path, checkpoint_data, "Completed all papers")
    print("Verification completed successfully for all remaining papers.")

if __name__ == "__main__":
    main()
