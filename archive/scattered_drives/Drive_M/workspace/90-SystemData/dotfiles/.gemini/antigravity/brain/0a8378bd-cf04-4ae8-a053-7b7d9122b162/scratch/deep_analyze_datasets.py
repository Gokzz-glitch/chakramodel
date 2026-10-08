import os
import sys
import json
import random
import tempfile
import zipfile
import numpy as np
import cv2

def analyze_zip(zip_path, max_img_samples=100, max_vid_samples=5):
    if not os.path.exists(zip_path):
        return {"error": "File not found"}
        
    counts = {
        "total_files": 0,
        "frames": 0,
        "masks": 0,
        "videos": 0,
        "weights": 0,
        "code": 0,
        "other": 0
    }
    
    samples = {
        "frames": [],
        "masks": [],
        "videos": []
    }
    
    resolutions = set()
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            members = z.infolist()
            for m in members:
                if m.is_dir(): continue
                counts["total_files"] += 1
                
                fname = m.filename.lower()
                ext = os.path.splitext(fname)[1]
                
                if ext in ['.mp4', '.avi', '.mkv', '.mov']:
                    counts["videos"] += 1
                    samples["videos"].append(m)
                elif ext in ['.jpg', '.jpeg', '.png', '.tif', '.bmp']:
                    if 'mask' in fname:
                        counts["masks"] += 1
                        samples["masks"].append(m)
                    else:
                        counts["frames"] += 1
                        samples["frames"].append(m)
                elif ext in ['.pt', '.pth', '.h5', '.onnx']:
                    counts["weights"] += 1
                elif ext in ['.py', '.ipynb', '.sh']:
                    counts["code"] += 1
                else:
                    counts["other"] += 1

            random.seed(42) # Deterministic
            # Sample for integrity
            frames_to_test = random.sample(samples["frames"], min(max_img_samples, len(samples["frames"])))
            masks_to_test = random.sample(samples["masks"], min(max_img_samples, len(samples["masks"])))
            videos_to_test = random.sample(samples["videos"], min(max_vid_samples, len(samples["videos"])))
            
            integrity = {
                "frames_tested": len(frames_to_test),
                "frames_healthy": 0,
                "masks_tested": len(masks_to_test),
                "masks_healthy": 0,
                "videos_tested": len(videos_to_test),
                "videos_healthy": 0
            }
            
            # Check frames
            for m in frames_to_test:
                try:
                    data = z.read(m.filename)
                    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                    if img is not None and img.std() > 1.0:
                        integrity["frames_healthy"] += 1
                        resolutions.add(f"{img.shape[1]}x{img.shape[0]}")
                except Exception:
                    pass
                    
            # Check masks
            for m in masks_to_test:
                try:
                    data = z.read(m.filename)
                    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        integrity["masks_healthy"] += 1
                        resolutions.add(f"{img.shape[1]}x{img.shape[0]}")
                except Exception:
                    pass

            # Check videos
            for m in videos_to_test:
                try:
                    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(m.filename.lower())[1], delete=False) as tmp:
                        tmp.write(z.read(m.filename))
                        tmp_path = tmp.name
                        
                    cap = cv2.VideoCapture(tmp_path)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            integrity["videos_healthy"] += 1
                            resolutions.add(f"{frame.shape[1]}x{frame.shape[0]}")
                    cap.release()
                    os.remove(tmp_path)
                except Exception:
                    pass
                    
            # Calculate Worth & Balance
            total_tested = integrity["frames_tested"] + integrity["masks_tested"] + integrity["videos_tested"]
            total_healthy = integrity["frames_healthy"] + integrity["masks_healthy"] + integrity["videos_healthy"]
            worth_percentage = (total_healthy / total_tested * 100) if total_tested > 0 else 100.0
            
            balance = "Balanced"
            if counts["frames"] > 0:
                mask_ratio = counts["masks"] / counts["frames"]
                if mask_ratio < 0.2:
                    balance = "Highly Imbalanced (Very few masks)"
                elif mask_ratio > 1.5:
                    balance = "Highly Imbalanced (More masks than frames?)"
                else:
                    balance = f"Balanced ({mask_ratio:.2f} masks/frame ratio)"
            elif counts["videos"] > 0:
                balance = "Video Dataset (Balance depends on video content)"

            return {
                "counts": counts,
                "integrity": integrity,
                "resolutions": list(resolutions),
                "balance": balance,
                "worth_percentage": worth_percentage,
                "is_genuine": total_healthy == total_tested
            }

    except Exception as e:
        return {"error": str(e)}

def main():
    target_dir = sys.argv[1]
    datasets = [
        "polypgen20021-video.zip",
        "ldpolypvideowithoutpolyps.zip",
        "ldpolypvideopolyponly.zip",
        "hperkvasir-labeled-videos-part2-002.zip",
        "hyperkvasir-labeled-videos-part2-001.zip",
        "endoscene-cvc300-polyp-raw-dataset.zip",
        "hyperkvasir-dataset-first-half-and-and-ld-dataset.zip",
        "polypdb-polyp-raw.zip",
        "cvc-sample-video.zip",
        "final-om-evlautation-upload.zip",
        "om-finalkaggle-upload.zip",
        "chakramodel-kaggle-code.zip",
        "chakratransformer-weights.zip",
        "chakramodel-evaluation-datasets.zip"
    ]
    
    results = {}
    print(f"Analyzing {len(datasets)} datasets in {target_dir}...")
    for ds in datasets:
        path = os.path.join(target_dir, ds)
        print(f"Analyzing {ds}...")
        res = analyze_zip(path)
        results[ds] = res
        print(f"  Result: {res.get('worth_percentage', 'N/A')}% worth.")
        
    out_path = os.path.join(target_dir, "deep_analysis_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deep_analyze_datasets.py <target_dir>")
        sys.exit(1)
    main()
