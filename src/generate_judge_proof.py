import os
import time
from pathlib import Path
from infer_stream import process_4way_video_streams

def generate_proof_for_judges(input_dir, output_base_dir, max_videos=5, conf_thresh=0.20):
    input_dir = Path(input_dir)
    output_base_dir = Path(output_base_dir)
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    weights_path = r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt"
    
    videos = sorted(list(input_dir.glob("*.avi")) + list(input_dir.glob("*.mp4")))
    print(f"==================================================")
    print(f"🎬 CHAKRAMODEL: GENERATING 4-WAY PROOF VIDEOS FOR JUDGES")
    print(f"Input Directory : {input_dir}")
    print(f"Output Directory: {output_base_dir}")
    print(f"Model Weights   : {weights_path}")
    print(f"Confidence      : {conf_thresh}")
    print(f"Total Videos    : {len(videos)}")
    print(f"==================================================\n")
    
    selected_videos = videos[:max_videos] if max_videos > 0 else videos
    
    summary_records = []
    
    for i, vid_path in enumerate(selected_videos, 1):
        vid_name = vid_path.stem
        vid_out_dir = output_base_dir / vid_name
        vid_out_dir.mkdir(parents=True, exist_ok=True)
        
        out_dict = {
            "raw": str(vid_out_dir / f"{vid_name}_1_RAW.mp4"),
            "baseline": str(vid_out_dir / f"{vid_name}_2_BASELINE_YOLO.mp4"),
            "kalman": str(vid_out_dir / f"{vid_name}_3_KALMAN_TRACKED.mp4"),
            "full": str(vid_out_dir / f"{vid_name}_4_CHAKRAMODEL_FULL.mp4"),
            "grid": str(output_base_dir / f"JUDGE_DEMO_2x2_GRID_{vid_name}.mp4"),
        }
        
        print(f"[{i}/{len(selected_videos)}] ⏳ Processing '{vid_path.name}'...")
        t_start = time.time()
        
        try:
            process_4way_video_streams(
                input_source=str(vid_path),
                output_dict=out_dict,
                model_path=weights_path,
                conf_thresh=conf_thresh
            )
            elapsed = time.time() - t_start
            print(f"   ✅ Done in {elapsed:.2f}s!")
            print(f"   🎥 Main Judge Demo Grid: {out_dict['grid']}\n")
            summary_records.append({
                "video": vid_path.name,
                "status": "SUCCESS",
                "time_sec": round(elapsed, 2),
                "grid_path": out_dict["grid"]
            })
        except Exception as e:
            print(f"   ❌ Error processing {vid_path.name}: {e}\n")
            summary_records.append({
                "video": vid_path.name,
                "status": f"FAILED: {e}",
                "time_sec": 0,
                "grid_path": "N/A"
            })
            
    print("==================================================")
    print("🏆 ALL JUDGE DEMO PROOF VIDEOS GENERATED!")
    print(f"Outputs are located at: {output_base_dir}")
    print("==================================================")
    
    # Write a clean text summary
    summary_file = output_base_dir / "JUDGE_PROOF_SUMMARY.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("CHAKRAMODEL - 4-QUADRANT COMPARATIVE PROOF FOR JUDGES\n")
        f.write("=" * 60 + "\n\n")
        f.write("QUADRANT LAYOUT IN 2x2 GRID DEMO VIDEOS:\n")
        f.write("┌───────────────────────────┬───────────────────────────┐\n")
        f.write("│ 1. RAW VIDEO FEED         │ 2. BASELINE YOLOv8        │\n")
        f.write("│ (Original Unprocessed)    │ (No Tracking / Flicker)   │\n")
        f.write("├───────────────────────────┼───────────────────────────┤\n")
        f.write("│ 3. YOLO + KALMAN FILTER   │ 4. CHAKRAMODEL FULL SUITE │\n")
        f.write("│ (ByteTrack Trajectory)    │ (Kalman+BoxHolder+Artifact)│\n")
        f.write("└───────────────────────────┴───────────────────────────┘\n\n")
        f.write("GENERATED PROOF FILES:\n")
        for rec in summary_records:
            f.write(f"- Video: {rec['video']} | Status: {rec['status']} | Time: {rec['time_sec']}s\n")
            f.write(f"  Grid Demo: {rec['grid_path']}\n\n")

if __name__ == "__main__":
    polyps_dir = r"M:\chakramodel\video_testing\polyp\extracted\videos with polyps"
    output_dir = r"M:\chakramodel\outputs\judge_proof"
    generate_proof_for_judges(polyps_dir, output_dir, max_videos=3, conf_thresh=0.18)
