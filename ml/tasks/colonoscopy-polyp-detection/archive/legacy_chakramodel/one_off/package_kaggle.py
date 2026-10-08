import os
import shutil
import zipfile
import json
from pathlib import Path

def create_notebook(package_dir):
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# ChakraModel: Kaggle Evaluation Pipeline\n",
                    "This notebook runs the Zero-Shot benchmarking, Ablation Study, and Clinical Robustness tests."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "!pip install ultralytics tabulate\n",
                    "import sys\n",
                    "sys.path.append('/kaggle/working/src')"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 1. Setup Datasets\n",
                    "Ensure you have added the required datasets to your Kaggle environment.\n",
                    "They should be mounted under `/kaggle/input/`."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import os\n",
                    "# We create symlinks in a 'data' folder so the scripts can find them easily\n",
                    "os.makedirs('/kaggle/working/data', exist_ok=True)\n",
                    "\n",
                    "# IMPORTANT: Adjust these paths based on what you name the datasets when you add them in Kaggle\n",
                    "dataset_mappings = {\n",
                    "    '/kaggle/input/kvasir-seg': '/kaggle/working/data/kvasir-seg',\n",
                    "    '/kaggle/input/cvc-clinicdb': '/kaggle/working/data/cvc-clinicdb',\n",
                    "    '/kaggle/input/etis-larib': '/kaggle/working/data/etis-larib',\n",
                    "    '/kaggle/input/cvc-colondb': '/kaggle/working/data/cvc-colondb',\n",
                    "    '/kaggle/input/cvc-300': '/kaggle/working/data/cvc-300'\n",
                    "}\n",
                    "\n",
                    "for src, dst in dataset_mappings.items():\n",
                    "    if os.path.exists(src) and not os.path.exists(dst):\n",
                    "        os.symlink(src, dst)\n",
                    "        print(f'Linked {src} -> {dst}')\n",
                    "    elif not os.path.exists(src):\n",
                    "        print(f'WARNING: {src} not found. Please attach the dataset to this notebook.')"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 2. Prepare Weights\n",
                    "Move the weights into the expected directory structure."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "os.makedirs('/kaggle/working/outputs/polyp_yolov8x/weights', exist_ok=True)\n",
                    "os.makedirs('/kaggle/working/weights', exist_ok=True)\n",
                    "\n",
                    "!cp /kaggle/working/best.pt /kaggle/working/outputs/polyp_yolov8x/weights/best.pt\n",
                    "!cp /kaggle/working/chakra_transformer_best.pth /kaggle/working/weights/chakra_transformer_best.pth"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 3. Run Zero-Shot Cross-Dataset Benchmark"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "!python /kaggle/working/src/evaluate_all.py"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 4. Run Ablation Study"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "!python /kaggle/working/src/ablation_study.py"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 5. Run Clinical Robustness Test"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "!python /kaggle/working/src/robustness_study.py"
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.12"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    nb_path = package_dir / "ChakraModel_Kaggle_Eval.ipynb"
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2)

def main():
    root = Path(__file__).resolve().parent
    package_dir = root / "kaggle_package"
    
    # 1. Create package directory
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    
    print("Copying Source Code...")
    shutil.copytree(root / "src", package_dir / "src")
    
    # Ensure metrics_engine_v2 is included in src for Kaggle pathing
    metrics_src = root / "metrics_engine_v2.py"
    if metrics_src.exists():
        shutil.copy2(metrics_src, package_dir / "src" / "metrics_engine_v2.py")
    
    print("Copying Weights...")
    # YOLO weights
    weights_dir = package_dir / "weights"
    weights_dir.mkdir(exist_ok=True)
    
    yolo_src = root / "weights" / "best.pt"
    if yolo_src.exists():
        shutil.copy2(yolo_src, weights_dir / "best.pt")
    else:
        print("WARNING: YOLO weights not found.")
        
    # PraNet weights (ChakraTransformer)
    pranet_src = root / "weights" / "chakra_transformer_best.pth"
    if pranet_src.exists():
        shutil.copy2(pranet_src, weights_dir / "chakra_transformer_best.pth")
    print("Skipping Test Videos (Lightweight Package Mode)...")
        
    print("Copying Kaggle Notebook...")
    shutil.copy2(root / "notebooks" / "Kaggle_ChakraTransformer_Evaluation.ipynb", package_dir / "Kaggle_ChakraTransformer_Evaluation.ipynb")
    
    print("Zipping package...")
    zip_path = root / "kaggle_upload.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for p in package_dir.rglob("*"):
            zipf.write(p, p.relative_to(package_dir))
            
    print(f"SUCCESS: Package created at {zip_path}")
    if zip_path.exists():
        print(f"Total size: {zip_path.stat().st_size / (1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
