import os
import re
import math

def parse_deep_extraction(file_path):
    papers = []
    if not os.path.exists(file_path): return papers
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    current_paper = None
    file_uri = "file:///" + file_path.replace("\\", "/")
    basename = os.path.basename(file_path)
    
    # Known subheaders that should NOT be treated as paper titles
    known_subheaders = [
        "authors", "abstract", "main points", "conclusion",
        "1. the", "2. the", "3. obstacles", "4. lit review", "5. future"
    ]
    
    for i, line in enumerate(content.split('\n')):
        line_num = i + 1
        line_str = line.strip()
        
        # Check if it's a ## header
        header_match = re.match(r'^##\s+(?:\[(.*?)\]|(.*))$', line_str)
        
        if header_match:
            raw_title = (header_match.group(1) or header_match.group(2)).strip()
            title_clean = raw_title.replace('*', '').strip()
            title_lower = title_clean.lower()
            
            # Check if this header is a KNOWN SUBHEADER
            is_subheader = False
            for ksh in known_subheaders:
                if title_lower.startswith(ksh):
                    is_subheader = True
                    break
                    
            if is_subheader:
                # Save previous capture
                if current_paper and current_paper["_current_section"] is not None:
                    sec = current_paper["_current_section"]
                    if sec == 1:
                        current_paper["problem"] += "\n" + "\n".join(current_paper["_capture"]).strip()
                    elif sec == 2:
                        current_paper["methodology"] += "\n" + "\n".join(current_paper["_capture"]).strip()
                    elif sec == 3:
                        current_paper["findings"] += "\n" + "\n".join(current_paper["_capture"]).strip()
                
                if current_paper:
                    current_paper["_capture"] = []
                    # Map the subheader to our columns
                    if title_lower.startswith("1.") or title_lower.startswith("abstract"):
                        current_paper["_current_section"] = 1
                    elif title_lower.startswith("2."):
                        current_paper["_current_section"] = 2
                    elif title_lower.startswith("3.") or title_lower.startswith("main points") or title_lower.startswith("conclusion"):
                        current_paper["_current_section"] = 3
                    else:
                        current_paper["_current_section"] = None
                continue

            # IF IT'S NOT A SUBHEADER, IT MUST BE A PAPER TITLE
            # Skip TOC headers
            if title_lower.startswith("table of contents") or title_lower.startswith("extracted information") or title_lower.startswith("paper summary") or title_lower.startswith("assessment of colonoscopy skill"):
                # Wait, "Assessment of colonoscopy skill..." is a real paper! Don't skip it.
                if "table of contents" in title_lower or "extracted information" in title_lower:
                    continue

            # We found a new paper
            ext_link = ""
            doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', raw_title, re.I)
            pmc_match = re.search(r'(PMC\d+)', raw_title, re.I)
            http_match = re.search(r'(https?://[^\s\)]+)', raw_title, re.I)
            
            if http_match:
                ext_link = f"[Link]({http_match.group(1)})"
            elif doi_match:
                doi_str = doi_match.group(0).rstrip(')')
                ext_link = f"[DOI](https://doi.org/{doi_str})"
            elif pmc_match:
                ext_link = f"[PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_match.group(1)})"
            
            local_link = f"[{basename}:L{line_num}]({file_uri}#L{line_num})"
            verification = f"{local_link} {ext_link}".strip()
                
            current_paper = {
                "title": title_clean,
                "core_tech": "N/A",
                "problem": "",
                "methodology": "",
                "findings": "",
                "verification": verification,
                "_current_section": None,
                "_capture": []
            }
            papers.append(current_paper)
            continue
            
        if not current_paper:
            continue
            
        # Extract Core ML Technology if present
        if line_str.startswith("**Core ML Technology:**"):
            current_paper["core_tech"] = line_str.replace("**Core ML Technology:**", "").strip()
            continue
            
        # Capture content if in a valid section
        if current_paper["_current_section"]:
            if line_str.startswith("* ") and (current_paper["_current_section"] in [1, 2, 3]) and not line_str.startswith("* What"):
                # some lists are findings, but we skip questions
                if not ("What is" in line_str or "What made" in line_str or "Why does" in line_str or "Are you doing" in line_str or "What framework" in line_str):
                    current_paper["_capture"].append(line_str)
            elif line_str and not line_str.startswith("*"):
                current_paper["_capture"].append(line_str)

    # Handle the last capture
    if current_paper and current_paper["_current_section"] is not None:
        sec = current_paper["_current_section"]
        if sec == 1:
            current_paper["problem"] += "\n" + "\n".join(current_paper["_capture"]).strip()
        elif sec == 2:
            current_paper["methodology"] += "\n" + "\n".join(current_paper["_capture"]).strip()
        elif sec == 3:
            current_paper["findings"] += "\n" + "\n".join(current_paper["_capture"]).strip()

    valid_papers = []
    for p in papers:
        # Clean up accumulated newlines
        p["problem"] = p["problem"].strip()
        p["methodology"] = p["methodology"].strip()
        p["findings"] = p["findings"].strip()
        
        # If it has absolutely nothing, skip it (junk header)
        if p['core_tech'] == 'N/A' and not p['problem'] and not p['methodology'] and not p['findings']:
            continue
            
        # If core_tech is missing but it has an abstract, mark it
        if p['core_tech'] == 'N/A' and p['problem']:
            p['core_tech'] = "See Abstract/Methodology"
            
        # For papers that use Abstract/Main Points, methodology might be empty but problem has Abstract
        if not p['methodology'] and p['problem']:
            p['methodology'] = "See Problem & Motivation (Abstract)"
            
        valid_papers.append(p)

    return valid_papers

def parse_pmc_file(file_path):
    if not os.path.exists(file_path): return []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    title = ""
    title_match = re.search(r'\*\*Title:\*\*\s*(.+)', content, re.I)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = os.path.basename(file_path)

    problem = []
    methodology = []
    findings = []
    
    current_section = None
    
    for line in content.split('\n'):
        line_str = line.strip()
        lower_line = line_str.lower()
        
        if re.match(r'^#+\s+.*objective', lower_line) or re.match(r'^#+\s+.*context', lower_line):
            current_section = 1
            continue
        elif re.match(r'^#+\s+.*methodology', lower_line) or re.match(r'^#+\s+.*ai model', lower_line):
            current_section = 2
            continue
        elif re.match(r'^#+\s+.*finding', lower_line) or re.match(r'^#+\s+.*result', lower_line):
            current_section = 3
            continue
        elif re.match(r'^#+\s+.*conclusion', lower_line) or re.match(r'^#+\s+.*future', lower_line):
            current_section = 4
            continue
        elif re.match(r'^#+\s+', line_str):
            current_section = None
            continue
            
        if current_section == 1 and line_str and not line_str.startswith("**Title:**"):
            problem.append(line_str)
        elif current_section == 2 and line_str:
            methodology.append(line_str)
        elif current_section == 3 and line_str:
            findings.append(line_str)
            
    pmc_id = re.search(r'(PMC\d+)', os.path.basename(file_path), re.I)
    ext_link = f"[PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id.group(1)})" if pmc_id else ""
    basename = os.path.basename(file_path)
    file_uri = "file:///" + file_path.replace("\\", "/")
    local_link = f"[{basename}:L1]({file_uri}#L1)"
    verification = f"{local_link} {ext_link}".strip()
    
    return [{
        "title": title,
        "core_tech": "See Methodology",
        "problem": " ".join(problem).strip(),
        "methodology": " ".join(methodology).strip(),
        "findings": " ".join(findings).strip(),
        "verification": verification
    }]

def format_cell(text, max_len=250):
    if not text: return "N/A"
    text = text.replace("|", ",").replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text

def main():
    directory = r"m:\chakramodel"
    files = [f for f in os.listdir(directory) if f.startswith("extracted_PMC") and f.endswith(".md")]
    
    all_papers = []
    
    # 1. Parse individual PMC files
    for filename in files:
        path = os.path.join(directory, filename)
        all_papers.extend(parse_pmc_file(path))
        
    # 2. Parse the aggregated deep extraction file
    main_file = "ml_colonoscopy_deep_extraction.md"
    main_path = os.path.join(directory, main_file)
    if os.path.exists(main_path):
        all_papers.extend(parse_deep_extraction(main_path))
        
    print(f"Extracted {len(all_papers)} VALID papers from markdown.")
    
    if len(all_papers) == 0:
        print("No valid papers found!")
        return

    # Delete old batch files so there's no confusion
    for i in range(1, 10):
        old_file = os.path.join(directory, f"paper_comparison_batch_{i}.md")
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except:
                pass

    # Split into 6 batches
    num_batches = 6
    batch_size = math.ceil(len(all_papers) / num_batches)
    
    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, len(all_papers))
        batch_papers = all_papers[start_idx:end_idx]
        
        if not batch_papers:
            break
            
        out_file = os.path.join(directory, f"verified_matrix_batch_{i+1}.md")
        with open(out_file, "w", encoding="utf-8") as out:
            out.write(f"# Comprehensive Paper Comparison Matrix - Batch {i+1} of {num_batches}\n\n")
            out.write("This matrix compiles the literature review data from all deep-extracted papers, split into batches.\n\n")
            out.write("| Paper Name | Core ML Technology | Problem & Motivation | Methodology | Obstacles & Breakthroughs | Verification Links |\n")
            out.write("|---|---|---|---|---|---|\n")
            
            for p in batch_papers:
                title = format_cell(p['title'], 80)
                core = format_cell(p['core_tech'], 80)
                prob = format_cell(p['problem'], 250)
                meth = format_cell(p['methodology'], 250)
                find = format_cell(p['findings'], 250)
                veri = p['verification']
                
                out.write(f"| {title} | {core} | {prob} | {meth} | {find} | {veri} |\n")
                
        print(f"Created {out_file} with {len(batch_papers)} papers.")

if __name__ == "__main__":
    main()
