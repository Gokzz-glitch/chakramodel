import os
import sys
import time
import zipfile
import json

TARGET_DIR = r"I:\My Drive\1509-chakramodelom\dataet"

EXPECTED = {
    "polypgen20021-video.zip": {
        "slug": "gokulraj324/polypgen20021-video",
        "expected_sizes": [3420255917],
        "expected_member_counts": [26918, 10000],
    },
    "endoscene-cvc300-polyp-raw-dataset.zip": {
        "slug": "gokulrocky/endoscene-cvc300-polyp-raw-dataset",
        "expected_sizes": [16459371],
        "expected_member_counts": [120],
    },
    "cvc-sample-video.zip": {
        "slug": "gokulrocky/cvc-sample-video",
        "expected_sizes": [4340196259, 4351232756],
        "expected_member_counts": [46, 21],
    },
    "hperkvasir-labeled-videos-part2-002.zip": {
        "slug": "gokulrocky/hperkvasir-labeled-videos-part2-002",
        "expected_sizes": [14687248757],
        "expected_member_counts": [188],
    },
    "hyperkvasir-labeled-videos-part2-001.zip": {
        "slug": "gokulrocky/hyperkvasir-labeled-videos-part2-001",
        "expected_sizes": [15423057945],
        "expected_member_counts": [189],
    },
    "hyperkvasir-dataset-first-half-and-and-ld-dataset.zip": {
        "slug": "gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset",
        "expected_sizes": [16544061303],
        "expected_member_counts": [41082],
    },
    "chakramodel-evaluation-datasets.zip": {
        "slug": "gokulrocky/chakramodel-evaluation-datasets",
        "expected_sizes": [99487305],
        "expected_member_counts": [3000],
    },
    "final-om-evlautation-upload.zip": {
        "slug": "gokulrocky/final-om-evlautation-upload",
        "expected_sizes": [1155170464, 1155167936],
        "expected_member_counts": [56, 55],
    },
    "ldpolypvideopolyponly.zip": {
        "slug": "gokulraj324/ldpolypvideopolyponly",
        "expected_sizes": [13189544842],
        "expected_member_counts": [82594],
    },
    "ldpolypvideowithoutpolyps.zip": {
        "slug": "gokulraj324/ldpolypvideowithoutpolyps",
        "expected_sizes": [13247306908],
        "expected_member_counts": [61],
    },
    "polypdb-polyp-raw.zip": {
        "slug": "gokulrocky/polypdb-polyp-raw",
        "expected_sizes": [1384993669],
        "expected_member_counts": [15736],
    },
}

def verify_archive(name, info):
    filepath = os.path.join(TARGET_DIR, name)
    partial_path = filepath + ".kaggle-partial"
    
    res = {
        "archive": name,
        "exists": os.path.exists(filepath),
        "partial_exists": os.path.exists(partial_path),
        "size_bytes": 0,
        "size_valid": False,
        "zip_valid": False,
        "bad_member": None,
        "member_count": 0,
        "count_valid": False,
        "uncompressed_bytes": 0,
        "duration_sec": 0,
        "error": None
    }
    
    if not res["exists"]:
        res["error"] = "File does not exist"
        return res
        
    res["size_bytes"] = os.path.getsize(filepath)
    res["size_valid"] = res["size_bytes"] in info["expected_sizes"]
    if not res["size_valid"]:
        res["error"] = f"Size mismatch: {res['size_bytes']} not in {info['expected_sizes']}"
        return res
        
    t0 = time.time()
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            infolist = z.infolist()
            res["member_count"] = len(infolist)
            non_dir = len([m for m in infolist if not m.is_dir()])
            res["uncompressed_bytes"] = sum(m.file_size for m in infolist)
            res["count_valid"] = (res["member_count"] in info["expected_member_counts"]) or (non_dir in info["expected_member_counts"])
            
            # testzip
            bad = z.testzip()
            res["bad_member"] = bad
            res["zip_valid"] = (bad is None)
    except Exception as e:
        res["error"] = str(e)
    res["duration_sec"] = round(time.time() - t0, 2)
    return res

if __name__ == "__main__":
    print(f"Starting independent empirical archive verification in {TARGET_DIR}...")
    results = {}
    all_ok = True
    for name, info in EXPECTED.items():
        print(f"Checking {name}...", flush=True)
        r = verify_archive(name, info)
        results[name] = r
        status = "PASS" if (r["exists"] and r["size_valid"] and not r["partial_exists"] and r["zip_valid"] and r["count_valid"]) else "FAIL"
        print(f"  -> {status} (size: {r['size_bytes']}, count: {r['member_count']}, bad: {r['bad_member']}, time: {r['duration_sec']}s, err: {r['error']})", flush=True)
        if status != "PASS":
            all_ok = False
            
    out_file = r"C:\Users\imgk3\.gemini\antigravity\scratch\challenger_m4_1\independent_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Done. Saved to {out_file}. Overall OK: {all_ok}")
    sys.exit(0 if all_ok else 1)
