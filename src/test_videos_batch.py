import os
import glob
import time
import argparse
from pathlib import Path
from infer_stream import process_4way_video_streams

def run_video_tests(video_dir, output_dir, max_videos=3, max_frames=300, conf_thresh=0.2):
    video_dir = Path(video_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    weights_path = r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt"
    
    video_files = sorted(list(video_dir.glob("*.avi")) + list(video_dir.glob("*.mp4")))
    # Exclude already analyzed files
    video_files = [v for v in video_files if not v.name.endswith("_analyzed.mp4") and not v.name.startswith("out_")]
    
    if not video_files:
        print(f"No video files found in {video_dir}")
        return
        
    print(f"Found {len(video_files)} test videos in {video_dir}.")
    selected_videos = video_files[:max_videos] if max_videos > 0 else video_files
    print(f"Testing {len(selected_videos)} videos with weights: {weights_path}")
    print("=" * 60)
    
    for idx, vid_path in enumerate(selected_videos, 1):
        vid_stem = vid_path.stem
        vid_out_dir = output_dir / vid_stem
        vid_out_dir.mkdir(parents=True, exist_ok=True)
        
        out_dict = {
            "raw": str(vid_out_dir / "1_raw.mp4"),
            "baseline": str(vid_out_dir / "2_baseline_yolo.mp4"),
            "kalman": str(vid_out_dir / "3_kalman_tracked.mp4"),
            "full": str(vid_out_dir / "4_chakramodel_full.mp4"),
            "grid": str(vid_out_dir / "combined_2x2_grid.mp4"),
        }
        
        print(f"\n[{idx}/{len(selected_videos)}] Processing: {vid_path.name}")
        t0 = time.time()
        
        process_4way_video_streams(
            input_source=str(vid_path),
            output_dict=out_dict,
            model_path=weights_path,
            conf_thresh=conf_thresh
        )
        
        elapsed = time.time() - t0
        print(f"Finished {vid_path.name} in {elapsed:.2f}s")
        print(f"-> 2x2 Grid Output saved at: {out_dict['grid']}")
        
    print("\n" + "=" * 60)
    print(f"All {len(selected_videos)} video tests completed! Results stored in: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video_dir", type=str, default=r"M:\chakramodel\video_testing")
    parser.add_argument("--output_dir", type=str, default=r"M:\chakramodel\outputs\test_results")
    parser.add_argument("--max_videos", type=int, default=2, help="Number of videos to test (0 for all)")
    parser.add_argument("--conf", type=float, default=0.20, help="Confidence threshold")
    args = parser.parse_args()
    
    run_video_tests(args.video_dir, args.output_dir, max_videos=args.max_videos, conf_thresh=args.conf)
