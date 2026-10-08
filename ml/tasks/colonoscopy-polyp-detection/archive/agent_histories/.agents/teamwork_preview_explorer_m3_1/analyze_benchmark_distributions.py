import json
from pathlib import Path
import numpy as np

eval_dir = Path(r"m:\chakramodel\outputs\eval")
benchmarks = ["kvasir-seg_benchmark.json", "cvc-clinicdb_benchmark.json", "cvc-colondb_benchmark.json", "cvc-300_benchmark.json", "etis_benchmark.json"]

print("="*105)
print(f"{'DATASET':<16} | {'N':<5} | {'DICE MEAN±STD':<16} | {'MEDIAN':<8} | {'IQR [25%-75%]':<16} | {'MIN':<7} | {'MAX':<7} | {'ZERO%':<6}")
print("="*105)

for b in benchmarks:
    fp = eval_dir / b
    if not fp.exists():
        continue
    data = json.loads(fp.read_text())
    name = data.get("dataset", b.replace("_benchmark.json", ""))
    n = data.get("n_images", len(data.get("per_image", [])))
    per_img = data.get("per_image", [])
    if not per_img:
        print(f"{name:<16} | {n:<5} | NO PER-IMAGE DATA")
        continue
    dices = np.array([x["dice"] for x in per_img])
    
    mean = np.mean(dices)
    std = np.std(dices)
    med = np.median(dices)
    q25, q75 = np.percentile(dices, [25, 75])
    min_d = np.min(dices)
    max_d = np.max(dices)
    zero_pct = (np.sum(dices < 0.05) / len(dices)) * 100.0
    
    print(f"{name:<16} | {n:<5} | {mean:.4f} ± {std:.4f}  | {med:.4f}  | [{q25:.3f} - {q75:.3f}]   | {min_d:.4f} | {max_d:.4f} | {zero_pct:4.1f}%")

print("="*105)
