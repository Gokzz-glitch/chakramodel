import json
import os
import sys
import torch
import torch.nn as nn
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"

def test_combo3_isolated():
    nb_path = os.path.join(NOTEBOOKS_DIR, "Combo3_AdaBN_ChakraNet.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    cells = {idx: "".join(cell.get("source", [])) for idx, cell in enumerate(nb["cells"])}
    
    env = {}
    exec("""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
from torch.cuda.amp import autocast
import numpy as np
import time
from pathlib import Path
class AdaBNConfig:
    batch_size = 32
    num_workers = 4
    device = 'cpu'
    epochs = 1
    n_adapt_batches = 2
config = AdaBNConfig()
""", env)
    
    # Cell 5: Model
    exec(cells[5], env)
    
    # Create dummy dataloader
    class DummyLoader:
        batch_size = 32
        def __iter__(self):
            for _ in range(5):
                yield torch.randn(2, 3, 352, 352)
    
    env["target_unlabelled_loader"] = DummyLoader()
    
    # Cell 7
    exec(cells[7], env)
    print("Combo 3 Cell 7 executed with dummy loader with ZERO errors!")

if __name__ == "__main__":
    test_combo3_isolated()
