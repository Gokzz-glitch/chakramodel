import json

with open('.agents/teamwork_preview_explorer_m1_1_gen2/slug_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Categorize slugs
categories = {
    "Target / Benchmark Polyp Datasets (Images, Videos, Masks)": [
        "debeshjha1/kvasirseg",
        "balraj98/cvcclinicdb",
        "ahaan2/cvc-clinicdb",
        "ivannikov2002/kvasir-seg-data-polyp-segmentation-detection",
        "tamimm91437/etis-laribpolypdb",
        "nguyenvoquocduong/etis-laribpolypdb",
        "gokulrocky/endoscene-cvc300-polyp-raw-dataset",
        "gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset",
        "gokulrocky/polypdb-polyp-raw-stress-testdataset",
        "gokulrocky/polypdataset-gokul",
        "gokulrocky/chakramodel-evaluation-datasets",
        "gokulrocky/chakramodel-yolo-combo-dataset"
    ],
    "Model Weights Datasets": [
        "gokulraj324/chakramodel-weights",
        "gokulraj324/chakramodel-weightsupdated4",
        "gokulrocky/chakramodel-weights",
        "gokulrocky/chakratransformer-weights",
        "gokulrocky/kaggle-upload-zip4"
    ],
    "Code / Workspace / Bundle Packages": [
        "gokulrocky/chakramodel",
        "gokulrocky/chakramodel-kaggle-code",
        "gokulrocky/chakramodel-kaggle-codethen",
        "gokulrocky/om-finalkaggle-upload",
        "gokulrocky/updated-kaggle"
    ]
}

report_lines = []
for cat, slugs in categories.items():
    report_lines.append(f"\n### {cat}\n")
    for s in slugs:
        info = data.get(s, {})
        report_lines.append(f"- **`{s}`** (Occurrences: {info.get('total_occurrences', 0)}, Files: {info.get('file_count', 0)})")
        report_lines.append(f"  URL: https://www.kaggle.com/datasets/{s}")
        report_lines.append(f"  Files: {', '.join(info.get('files', [])[:6])}")

with open('.agents/teamwork_preview_explorer_m1_1_gen2/summary_breakdown.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))

print("Breakdown written successfully.")
