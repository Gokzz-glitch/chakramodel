import os
import re

def parse_markdown_for_papers(file_path):
    papers = []
    if not os.path.exists(file_path): return papers
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple parsing heuristic
    # This might depend on the structure of the markdown file
    sections = re.split(r'(?:^|\n)##\s+Paper:\s*', content)
    for section in sections[1:]:
        lines = section.strip().split('\n')
        title = lines[0].strip()
        
        # default values
        year = "N/A"
        backbone = "N/A"
        datasets = "N/A"
        metrics = "N/A"
        best_dsc = "N/A"
        novelty = "N/A"
        
        for line in lines:
            line_l = line.lower()
            if line_l.startswith("- **year**:") or line_l.startswith("**year**:"):
                year = line.split(":", 1)[1].strip()
            elif line_l.startswith("- **backbone**:") or line_l.startswith("**backbone**:"):
                backbone = line.split(":", 1)[1].strip()
            elif line_l.startswith("- **datasets**:") or line_l.startswith("**datasets**:"):
                datasets = line.split(":", 1)[1].strip()
            elif line_l.startswith("- **metrics**:") or line_l.startswith("**metrics**:"):
                metrics = line.split(":", 1)[1].strip()
            elif line_l.startswith("- **best dsc") or line_l.startswith("**best dsc"):
                best_dsc = line.split(":", 1)[1].strip()
            elif line_l.startswith("- **novelty**:") or line_l.startswith("**novelty**:"):
                novelty = line.split(":", 1)[1].strip()
        
        papers.append({
            "title": title, "year": year, "backbone": backbone,
            "datasets": datasets, "metrics": metrics, "best_dsc": best_dsc,
            "novelty": novelty
        })
    return papers

def main():
    directory = r"m:\chakramodel"
    files = [f for f in os.listdir(directory) if f.startswith("extracted_PMC") and f.endswith(".md")]
    files.append("ml_colonoscopy_deep_extraction.md")
    
    all_papers = []
    for filename in files:
        path = os.path.join(directory, filename)
        papers = parse_markdown_for_papers(path)
        all_papers.extend(papers)
        
    print(f"Extracted {len(all_papers)} papers.")
    
    with open(r"m:\chakramodel\paper_comparison.md", "w", encoding="utf-8") as out:
        out.write("# Comprehensive Paper Comparison Matrix\n\n")
        out.write("| Paper Name | Year | Backbone | Datasets | Metrics | Best DSC/mIoU | Novelty |\n")
        out.write("|---|---|---|---|---|---|---|\n")
        
        for p in all_papers:
            # Escape pipes
            for k in p:
                p[k] = p[k].replace("|", ",")
            out.write(f"| {p['title'][:40]}... | {p['year']} | {p['backbone'][:30]} | {p['datasets'][:30]} | {p['metrics'][:30]} | {p['best_dsc'][:30]} | {p['novelty'][:50]}... |\n")
            
if __name__ == "__main__":
    main()
