import json
from pathlib import Path

files = {
    "notebookb6c3100a14.ipynb":     r"C:\Users\imgk3\Downloads\notebookb6c3100a14.ipynb",
    "notebookb6c3100a14 (1).ipynb": r"C:\Users\imgk3\Downloads\notebookb6c3100a14 (1).ipynb",
    "notebookb6c3100a14 (2).ipynb": r"C:\Users\imgk3\Downloads\notebookb6c3100a14 (2).ipynb",
    "FIXED.ipynb":                   r"C:\Users\imgk3\Downloads\Kaggle_ChakraTransformer_Evaluation_Standalone_FIXED.ipynb",
}

def get_all_source(nb):
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")

def check(src, pattern):
    return "YES" if pattern in src else "NO"

results = {}
for label, path in files.items():
    try:
        with open(path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        cells = nb["cells"]
        n_cells = len(cells)
        
        # First markdown cell title
        title = ""
        for c in cells:
            if c["cell_type"] == "markdown":
                title = "".join(c["source"])[:120].replace("\n", " ")
                break
        
        # All source combined
        all_src = get_all_source(nb)
        
        # Per-cell source
        code_cells = [c for c in cells if c["cell_type"] == "code"]
        
        results[label] = {
            "n_cells": n_cells,
            "title": title,
            # Architecture checks
            "decode_head": check(all_src, "decode_head"),
            "stage1_stage2": check(all_src, "stage1"),
            "ProgressiveDecoderBlock": check(all_src, "ProgressiveDecoderBlock"),
            # Safety checks
            "USE_AMP": check(all_src, "USE_AMP"),
            "pre_flight_diag": check(all_src, "model_keys - ckpt_keys"),
            "cell_1b_tree": check(all_src, "Contents of /kaggle/input"),
            "find_dataset_root": check(all_src, "find_dataset_root"),
            # install check
            "torchvision_pip": check(all_src, "pip install torchvision"),
            "timm_install": check(all_src, "timm"),
            # split check
            "kvasir_split": check(all_src, "np.random.seed(42)"),
            "weights_only": check(all_src, "weights_only=True"),
            "strict_true": check(all_src, "strict=True"),
            # IoU formula check (1e6 vs 1e-6 bug)
            "iou_bug_1e6": check(all_src, "1e6)"),
            "iou_correct_1e-6": check(all_src, "+ 1e-6)"),
        }
    except FileNotFoundError:
        results[label] = {"ERROR": "File not found"}
    except Exception as e:
        results[label] = {"ERROR": str(e)}

# Print comparison table
labels = list(results.keys())
checks = [
    ("Total Cells",         "n_cells"),
    ("decode_head arch",    "decode_head"),
    ("4-stage (stage1..4)", "stage1_stage2"),
    ("ProgressiveDecoderBlock", "ProgressiveDecoderBlock"),
    ("USE_AMP (CPU safe)",  "USE_AMP"),
    ("Pre-flight key diag", "pre_flight_diag"),
    ("Cell 1b /input tree", "cell_1b_tree"),
    ("find_dataset_root",   "find_dataset_root"),
    ("torchvision pip",     "torchvision_pip"),
    ("timm install",        "timm_install"),
    ("Kvasir seed(42) split","kvasir_split"),
    ("weights_only=True",   "weights_only"),
    ("strict=True load",    "strict_true"),
    ("IoU bug (1e6 bad)",   "iou_bug_1e6"),
    ("IoU fix (1e-6 ok)",   "iou_correct_1e-6"),
]

col_w = 26
header = f"{'Check':<26}" + "".join(f"{l:<28}" for l in labels)
print(header)
print("-" * len(header))
for desc, key in checks:
    row = f"{desc:<26}"
    for label in labels:
        val = results[label].get(key, "?")
        row += f"{str(val):<28}"
    print(row)

print()
print("TITLES:")
for label, data in results.items():
    print(f"  {label}: {data.get('title','?')}")
