import argparse, yaml, subprocess, sys
from pathlib import Path


def _resolve_weights(weights_arg: str, profile_cfg: dict) -> str:
    candidates: list[str] = []
    if weights_arg:
        candidates.append(weights_arg)
    candidates.extend(["best.pt", "last.pt", "yolov8n.pt"])

    cfg_model = str(profile_cfg.get("train", {}).get("model", "")).strip()
    if cfg_model:
        candidates.append(cfg_model)

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if candidate == "yolov8n.pt":
            return candidate
        if Path(candidate).exists():
            return candidate
    return "yolov8n.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["local","colab","docker"], required=True)
    ap.add_argument("--source", required=True, help="video path for inference")
    ap.add_argument("--weights", default="", help="YOLO weights path (auto-fallback: best.pt -> last.pt -> yolov8n.pt)")
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
    weights = _resolve_weights(args.weights, cfg)
    print(f"Using weights: {weights}")

    infer_cmd = [
        sys.executable, "src/hybrid_refine.py",
        "--source", args.source,
        "--yolo_weights", weights,
        "--out", args.out,
        "--conf", conf,
        "--uncertain_th", uncertain_th
    ]
    print("Running inference:", " ".join(infer_cmd))
    subprocess.run(infer_cmd, check=True)

    if args.run_eval:
        if not (args.gt_dir and args.pred_dir and args.images_dir):
            raise SystemExit("For --run_eval provide --gt_dir --pred_dir --images_dir")
        for name, raw_path in (("gt_dir", args.gt_dir), ("pred_dir", args.pred_dir), ("images_dir", args.images_dir)):
            path = Path(raw_path)
            if not path.exists() or not path.is_dir():
                raise SystemExit(f"{name} does not exist or is not a directory: {path}")
        eval_cmd = [
            sys.executable, "src/eval_pipeline.py",
            "--labels_dir", args.gt_dir,
            "--predictions_dir", args.pred_dir,
            "--images_dir", args.images_dir,
            "--out_dir", args.eval_out,
            "--iou_threshold", str(cfg.get("eval", {}).get("iou", 0.5))
        ]
        print("Running eval:", " ".join(eval_cmd))
        subprocess.run(eval_cmd, check=True)

if __name__ == "__main__":
    main()
