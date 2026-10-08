import argparse, yaml, subprocess, sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["local","colab","docker"], required=True)
    ap.add_argument("--source", required=True, help="video path for inference")
    ap.add_argument("--weights", required=True, help="YOLO weights path")
    ap.add_argument("--out", default="outputs/profile_demo.mp4")
    ap.add_argument("--run_eval", action="store_true")
    ap.add_argument("--gt_dir", default="")
    ap.add_argument("--pred_dir", default="")
    ap.add_argument("--images_dir", default="")
    ap.add_argument("--eval_out", default="outputs/eval")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(f"configs/profiles/{args.profile}.yaml").read_text(encoding="utf-8"))
    infer = cfg.get("infer", {})
    hybrid = cfg.get("hybrid", {})

    conf = str(infer.get("conf", 0.25))
    uncertain_th = str(hybrid.get("uncertain_th", 0.45))

    infer_cmd = [
        sys.executable, "src/hybrid_refine.py",
        "--source", args.source,
        "--yolo_weights", args.weights,
        "--out", args.out,
        "--conf", conf,
        "--uncertain_th", uncertain_th
    ]
    print("Running inference:", " ".join(infer_cmd))
    subprocess.run(infer_cmd, check=True)

    if args.run_eval:
        if not (args.gt_dir and args.pred_dir and args.images_dir):
            raise SystemExit("For --run_eval provide --gt_dir --pred_dir --images_dir")
        eval_cmd = [
            sys.executable, "src/eval_pipeline.py",
            "--gt_dir", args.gt_dir,
            "--pred_dir", args.pred_dir,
            "--images_dir", args.images_dir,
            "--out_dir", args.eval_out,
            "--iou", str(cfg.get("eval", {}).get("iou", 0.5))
        ]
        print("Running eval:", " ".join(eval_cmd))
        subprocess.run(eval_cmd, check=True)

if __name__ == "__main__":
    main()
