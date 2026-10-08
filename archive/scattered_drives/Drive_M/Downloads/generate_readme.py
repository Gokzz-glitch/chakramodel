import os

catalog_file = r"C:\Users\imgk3\.gemini\antigravity\brain\ed10122d-e091-4566-9916-252437fa3b14\draft_code_catalog.md"
readme_file = r"D:\ChakraModelPro\README.md"

header = """# ChakraModel Pro: Polyp Detection

Welcome to the master repository for the ChakraModel Polyp Detection project. This repository contains the complete codebase for the student-teacher knowledge distillation architecture designed for real-time, high-accuracy colonoscopy analysis.

## Overview
- **Teacher Model:** PraNetMicroRefiner (ResNet-101 backbone) - provides high-fidelity pseudo-labels.
- **Student Model:** ChakraTransformerSegmenter (ViT-Large backbone) - optimized for fast inference on clinical devices.
- **Primary Datasets:** Kvasir-SEG, CVC-ClinicDB, CVC-300, ETIS-LaribPolypDB, Piccolo, and PolypGen.

Below is a comprehensive catalog of the code and automation scripts available in this repository.

"""

try:
    with open(catalog_file, 'r', encoding='utf-8') as f:
        catalog_lines = f.readlines()
        
    # Skip the first few lines of the draft catalog since they are intro text for the agent UI
    catalog_content = ""
    start_collecting = False
    for line in catalog_lines:
        if line.startswith("## "):
            start_collecting = True
        if start_collecting:
            # Clean up the file:// paths to be relative markdown links for GitHub/VScode
            if "](file:///" in line:
                # Extract filename and construct a relative link
                parts = line.split("|")
                if len(parts) >= 4:
                    script_col = parts[1].strip()
                    path_col = parts[2].strip()
                    # path_col is like `scripts/something.py`
                    clean_path = path_col.replace('`', '')
                    script_name = clean_path.split('/')[-1].split('\\')[-1]
                    parts[1] = f" [{script_name}]({clean_path}) "
                    line = "|".join(parts)
            catalog_content += line
            
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write(catalog_content)
        
    print(f"Master README successfully generated at {readme_file}")
except Exception as e:
    print(f"Error: {e}")
