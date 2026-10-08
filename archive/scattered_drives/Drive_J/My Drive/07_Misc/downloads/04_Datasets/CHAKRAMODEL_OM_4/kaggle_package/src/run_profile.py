import argparse, yaml, subprocess, sys
from pathlib import Path
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["local","colab","docker"], required=True)
    ap.add_argument("--data", default="configs/data.yaml")
    args = ap.parse_args()
    p = Path(f"configs/profiles/{args.profile}.yaml")
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    t = cfg["train"]
    cmd = [
        sys.executable, "src/train_yolo.py",
        "--data", args.data,
        "--model", str(t["model"]),
        "--epochs", str(t["epochs"]),
        "--imgsz", str(t["imgsz"]),
        "--batch", str(t["batch"]),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
if __name__ == "__main__":
    main()
