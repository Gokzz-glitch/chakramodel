import os
import glob
import torch
import torch.nn as nn
from PIL import Image
import torchvision.transforms as T
from torch.utils.data import DataLoader
from metrics_engine_v2 import MetricsEngineV2
from cost_profiler import CostProfiler
from dataset_downloader import MultiDatasetManager
from statistical_significance import StatisticalSignificance

class RealDataset(torch.utils.data.Dataset):
    def __init__(self, img_dir, mask_dir, num_samples=100):
        self.img_paths = sorted(glob.glob(os.path.join(img_dir, "*.jpg")))[:num_samples]
        self.mask_dir = mask_dir
        self.transform = T.Compose([
            T.Resize((448, 448)),
            T.ToTensor()
        ])
        
    def __len__(self):
        return len(self.img_paths)
        
    def __getitem__(self, idx):
        img_path = self.img_paths[idx]
        basename = os.path.basename(img_path)
        mask_path = os.path.join(self.mask_dir, basename)
        
        img = Image.open(img_path).convert("RGB")
        if os.path.exists(mask_path):
            mask = Image.open(mask_path).convert("L")
        else:
            mask = Image.new("L", img.size)
            
        img_t = self.transform(img)
        mask_t = self.transform(mask)
        mask_t = (mask_t > 0.5).float() # binary
        
        return img_t, mask_t

class UnifiedEvaluator:
    """
    Master Evaluation Script for ChakraModel
    Executes cross-dataset evaluation across all 6 paradigms to satisfy MICCAI generalization requirements.
    """
    def __init__(self, models, datasets_dir="./datasets"):
        self.models = models
        self.datasets_dir = datasets_dir
        self.metrics_engine = MetricsEngineV2()
        self.profiler = CostProfiler()
        self.results = {}

    def get_dataloaders(self):
        img_dir = os.path.join(self.datasets_dir, "colon_cancer_dataset", "segmented-images", "images")
        mask_dir = os.path.join(self.datasets_dir, "colon_cancer_dataset", "segmented-images", "masks")
        ds = RealDataset(img_dir, mask_dir, num_samples=20)
        loader = DataLoader(ds, batch_size=4, shuffle=False)
        return {"ColonCancerDataset": loader}

    def run_evaluation(self):
        loaders = self.get_dataloaders()
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        for name, model in self.models.items():
            print(f"\n--- Profiling Cost for {name} ---")
            cost_metrics = self.profiler.profile_model(model, input_size=(1, 3, 448, 448), device=device)
            self.results[name] = {"Cost": cost_metrics, "Datasets": {}}
            
            model = model.to(device)
            model.eval()
            with torch.no_grad():
                for ds_name, loader in loaders.items():
                    print(f"Evaluating {name} on {ds_name}...")
                    
                    agg_metrics = {"Dice": [], "mIoU": [], "wF-measure": [], "S-measure": [], "E-measure": [], "MAE": []}
                    
                    for x, tgt in loader:
                        x, tgt = x.to(device), tgt.to(device)
                        pred = torch.sigmoid(model(x))
                        for b in range(x.size(0)):
                            res = self.metrics_engine.compute_all(pred[b:b+1], tgt[b:b+1])
                            for k, v in res.items():
                                agg_metrics[k].append(v)
                                
                    self.results[name]["Datasets"][ds_name] = {k: sum(v)/len(v) for k, v in agg_metrics.items()}

    def generate_report(self):
        print("\n=== CHAKRAMODEL UNIFIED EVALUATION REPORT ===")
        for name, data in self.results.items():
            print(f"\nModel: {name}")
            print("Cost Profile:", data["Cost"])
            for ds, metrics in data["Datasets"].items():
                print(f"  Dataset: {ds} -> Dice: {metrics['Dice']:.4f}, mIoU: {metrics['mIoU']:.4f}")

if __name__ == "__main__":
    import sys
    print("WARNING: evaluate_all.py is deprecated. Use src/evaluate_all.py for the actual evaluation pipeline.")
    sys.exit(1)
