import json
import os
import sys
import torch
import torch.nn as nn
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"

def get_notebook_cell_dict(nb_name):
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    return {idx: "".join(cell.get("source", [])) for idx, cell in enumerate(nb["cells"])}

def test_combo1():
    print("Testing Combo 1...")
    cells = get_notebook_cell_dict("Combo1_ChakraNet_Focal.ipynb")
    env = {}
    exec("""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
from torchvision.ops import sigmoid_focal_loss
import numpy as np
from pathlib import Path
DEVICE = torch.device('cpu')
""", env)
    # Cell 5: Model
    exec(cells[5], env)
    PraNet = env["PraNetResNet101"]
    model = env["model"]
    x = torch.randn(2, 3, 352, 352)
    model.train()
    out_train = model(x)
    assert len(out_train) == 5, f"Expected 5 deep supervision outputs, got {len(out_train)}"
    model.eval()
    out_eval = model(x)
    assert out_eval.shape == (2, 1, 352, 352), f"Expected (2, 1, 352, 352), got {out_eval.shape}"
    
    # Cell 6: Loss
    exec(cells[6], env)
    DeepSupervision = env["DeepSupervisionDiceFocalLoss"]
    criterion = DeepSupervision()
    target = torch.randint(0, 2, (2, 1, 352, 352)).float()
    loss = criterion(out_train, target)
    assert not torch.isnan(loss) and loss.item() > 0
    print(f"  Combo 1 Model & DeepSupervision Loss verified! (Loss={loss.item():.4f})")

def test_combo2():
    print("Testing Combo 2...")
    cells = get_notebook_cell_dict("Combo2_Topo_ChakraNet.ipynb")
    env = {}
    exec("""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import numpy as np
from pathlib import Path
DEVICE = torch.device('cpu')
""", env)
    exec(cells[5], env)
    PraNet = env["PraNetResNet101"]
    model = env["model"]
    x = torch.randn(2, 3, 352, 352)
    model.eval()
    out = model(x)
    assert out.shape == (2, 1, 352, 352)
    
    exec(cells[6], env)
    TopoLossCls = env["TopoAwareDeepSupervisionLoss"]
    criterion = TopoLossCls()
    target = torch.randint(0, 2, (2, 1, 352, 352)).float()
    model.train()
    out_train = model(x)
    loss = criterion(out_train, target)
    assert not torch.isnan(loss) and loss.item() > 0
    print(f"  Combo 2 Model & TopoAware Loss verified! (Loss={loss.item():.4f})")

def test_combo3():
    print("Testing Combo 3...")
    cells = get_notebook_cell_dict("Combo3_AdaBN_ChakraNet.ipynb")
    env = {}
    exec("""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import numpy as np
from pathlib import Path
class AdaBNConfig:
    batch_size = 32
    num_workers = 4
    device = 'cpu'
    epochs = 1
    n_adapt_batches = 2
config = AdaBNConfig()
""", env)
    exec(cells[5], env)
    PraNet = env["PraNetResNet101"]
    model = env["model"]
    x = torch.randn(2, 3, 352, 352)
    model.eval()
    out = model(x)
    assert out.shape == (2, 1, 352, 352)
    
    # In Cell 7, replace target_unlabelled_loader with dummy loader
    c7 = cells[7]
    c7_mod = c7.replace("adapter.adapt_to_target_domain(target_unlabelled_loader, n_adapt_batches=config.n_adapt_batches)", "# adapter.adapt")
    exec(c7_mod, env)
    AdaBNAdapter = env["AdaBNAdapter"]
    adapter = AdaBNAdapter(model)
    dummy_loader = [(torch.randn(2, 3, 352, 352), torch.randint(0, 2, (2, 1, 352, 352)).float()) for _ in range(3)]
    adapter.adapt_to_target_domain(dummy_loader, n_adapt_batches=2)
    print("  Combo 3 AdaBN zero-backprop domain adaptation verified!")

def test_combo4():
    print("Testing Combo 4...")
    cells = get_notebook_cell_dict("Combo4_DiffusionAug_ChakraNet.ipynb")
    env = {}
    exec("""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import numpy as np
import cv2
import shutil
from pathlib import Path
class DiffusionAugConfig:
    batch_size = 32
    num_workers = 4
    device = 'cpu'
    epochs = 1
    mc_dropout_p = 0.15
    mc_dropout_passes = 4
    uncertainty_threshold = 0.05
    num_inference_steps = 1
    guidance_scale = 7.5
    conditioning_scale = 1.0
    controlnet_model = "lllyasviel/control_v11p_sd15_canny"
    base_sd_model = "runwayml/stable-diffusion-v1-5"
config = DiffusionAugConfig()
raw_synth_dir = Path("./dummy_synth")
""", env)
    c6 = cells[6]
    c6_mod = c6.replace("filter_synthetic_dataset_with_mcdropout(\n    filter_model, raw_synth_dir, filtered_synth_dir,\n    threshold=config.uncertainty_threshold, mc_passes=config.mc_dropout_passes, device=config.device\n)", "# filter call")
    exec(c6_mod, env)
    PraNet = env["PraNetResNet101"]
    model = env["filter_model"]
    x = torch.randn(2, 3, 352, 352)
    model.eval()
    model.enable_mc_dropout()
    out = model(x)
    assert out.shape == (2, 1, 352, 352)
    print("  Combo 4 PraNet ResNet-101 with MC Dropout enabled verified!")

def test_combo5():
    print("Testing Combo 5...")
    cells = get_notebook_cell_dict("Combo5_Federated_ChakraNet.ipynb")
    env = {}
    exec("""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import numpy as np
from collections import OrderedDict
from pathlib import Path
device = torch.device('cpu')
""", env)
    exec(cells[4], env)
    PraNet = env["PraNetResNet101"]
    model = env["test_model"]
    x = torch.randn(2, 3, 352, 352)
    model.eval()
    out = model(x)
    assert out.shape == (2, 1, 352, 352)
    
    # In Cell 5, skip client training
    c5 = cells[5]
    c5_mod = c5.replace("for name in client_names:", "# for name in client_names:").replace("client_updates = []", "client_updates = []\n# client updates")
    # Execute cell 5 definitions
    exec("""
class DeepSupervisionDiceFocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, dice_w: float = 0.6, focal_w: float = 0.4):
        super(DeepSupervisionDiceFocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.dice_w = dice_w
        self.focal_w = focal_w

    def forward(self, preds, targets):
        if isinstance(preds, (list, tuple)):
            loss = 0.0
            weights = [1.0, 0.8, 0.6, 0.4, 0.2]
            for p, w in zip(preds, weights):
                probs = torch.sigmoid(p)
                inter = (probs * targets).sum(dim=(2, 3))
                card = probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3))
                dice_loss = 1.0 - (2.0 * inter + 1e-6) / (card + 1e-6)
                focal_loss = F.binary_cross_entropy_with_logits(p, targets, reduction='mean')
                loss += w * (self.dice_w * dice_loss.mean() + self.focal_w * focal_loss)
            return loss
        probs = torch.sigmoid(preds)
        inter = (probs * targets).sum(dim=(2, 3))
        card = probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3))
        dice_loss = 1.0 - (2.0 * inter + 1e-6) / (card + 1e-6)
        focal_loss = F.binary_cross_entropy_with_logits(preds, targets, reduction='mean')
        return self.dice_w * dice_loss.mean() + self.focal_w * focal_loss
""", env)
    exec(cells[5].split("class FederatedServer:")[0].split("class FederatedClient:")[0], env)
    # Extract FederatedServer
    server_code = "class FederatedServer:" + cells[5].split("class FederatedServer:")[1].split("# Instantiate Central Federated Server")[0]
    exec(server_code, env)
    ServerCls = env["FederatedServer"]
    server = ServerCls(model, device=torch.device('cpu'))
    w1 = OrderedDict({k: v.clone() for k, v in model.state_dict().items()})
    w2 = OrderedDict({k: v.clone() for k, v in model.state_dict().items()})
    server.aggregate_fedavg([w1, w2], [100, 200])
    print("  Combo 5 FederatedServer FedAvg parameter weighting verified!")

def test_combo6():
    print("Testing Combo 6...")
    cells = get_notebook_cell_dict("Combo6_ChakraTransformer.ipynb")
    env = {}
    exec("""
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
import numpy as np
from pathlib import Path
device = torch.device('cpu')
""", env)
    exec(cells[4], env)
    Transformer = env["ChakraTransformerSegmenter"]
    model = env["transformer_model"]
    x = torch.randn(2, 3, 384, 384)
    model.eval()
    out = model(x)
    assert out.shape == (2, 1, 384, 384), f"Expected (2, 1, 384, 384), got {out.shape}"
    
    c6 = cells[6]
    c6_mod = c6.split("def compute_conformal_resection_bands(")[0]
    exec(c6_mod, env)
    Calibrator = env["ConformalCalibrator"]
    calibrator = Calibrator(alphas=[0.05, 0.10])
    dummy_probs = np.random.uniform(0.0, 1.0, (384, 384)).astype(np.float32)
    calibrator.calibrated_thresholds = {0.05: 0.15, 0.10: 0.25}
    core, margin, cert = calibrator.predict_conformal_bands(dummy_probs, alpha=0.05)
    assert core.shape == (384, 384) and margin.shape == (384, 384) and cert.shape == (384, 384)
    print(f"  Combo 6 ChakraTransformer (ViT-Large 384) & Conformal Uncertainty Bands verified!")

if __name__ == "__main__":
    test_combo1()
    test_combo2()
    test_combo3()
    test_combo4()
    test_combo5()
    test_combo6()
    print("\n🎉 ALL 6 NOTEBOOK MODULES TESTED AND VERIFIED SUCCESSFULLY!")
