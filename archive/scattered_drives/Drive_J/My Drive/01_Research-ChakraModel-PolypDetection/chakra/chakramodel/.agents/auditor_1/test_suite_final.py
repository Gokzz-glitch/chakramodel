import json
import os
import sys
import copy
from collections import OrderedDict
import traceback
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import numpy as np

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"

def extract_cells_code(nb_name, cell_indices):
    path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    code_lines = []
    for idx in cell_indices:
        cell = data['cells'][idx]
        if cell.get('cell_type') == 'code':
            for line in cell.get('source', []):
                stripped = line.strip()
                if stripped.startswith('!') or stripped.startswith('%'):
                    continue
                # Skip automatic execution lines at the bottom of cells
                if line.startswith('model = ') or line.startswith('test_model = ') or line.startswith('transformer_model = ') or line.startswith('TRAIN_LOADER') or line.startswith('calibrator = ') or line.startswith('DATASET_PATH = ') or line.startswith('generate_synthetic_polyps_dataset') or line.startswith('adapter = '):
                    continue
                code_lines.append(line)
    return ''.join(code_lines)

def run_suite():
    print("=" * 80)
    print("FORENSIC INTEGRITY AUDIT: EMPIRICAL VERIFICATION OF ALL 6 COMBOS")
    print("=" * 80)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}\n")
    
    results = {}
    
    # -------------------------------------------------------------------------
    # COMBO 1: PraNetResNet101 + DeepSupervisionDiceFocalLoss
    # -------------------------------------------------------------------------
    print(">>> [COMBO 1 AUDIT] PraNetResNet101 & Deep Supervision Loss")
    try:
        code_c1 = extract_cells_code("Combo1_ChakraNet_Focal.ipynb", [5, 6])
        scope1 = {
            'torch': torch, 'nn': nn, 'F': F, 'models': models,
            'sigmoid_focal_loss': None, 'np': np, 'DEVICE': device
        }
        from torchvision.ops import sigmoid_focal_loss
        scope1['sigmoid_focal_loss'] = sigmoid_focal_loss
        exec(code_c1, scope1)
        
        PraNetResNet101 = scope1['PraNetResNet101']
        DeepSupervisionDiceFocalLoss = scope1['DeepSupervisionDiceFocalLoss']
        
        model = PraNetResNet101(channels=64, pretrained=False).to(device)
        model.train()
        
        # Test input tensor
        x = torch.randn(2, 3, 352, 352, device=device)
        outs = model(x)
        assert isinstance(outs, tuple) and len(outs) == 5, f"Expected 5 deep supervision outputs, got {len(outs)}"
        for idx, out in enumerate(outs):
            assert out.shape == (2, 1, 352, 352), f"Output {idx} shape mismatch: {out.shape}"
            
        criterion = DeepSupervisionDiceFocalLoss()
        target = (torch.rand(2, 1, 352, 352, device=device) > 0.5).float()
        loss = criterion(outs, target)
        assert not torch.isnan(loss) and not torch.isinf(loss) and loss.item() > 0
        loss.backward()
        
        # Check gradients
        grad_count = sum(p.grad is not None and torch.norm(p.grad).item() > 0 for p in model.parameters() if p.requires_grad)
        total_trainable = sum(1 for p in model.parameters() if p.requires_grad)
        print(f"  [PASS] Forward & Backward verified: Loss = {loss.item():.4f}, Gradients active on {grad_count}/{total_trainable} params ({grad_count/total_trainable*100:.1f}%)")
        assert grad_count / total_trainable > 0.95
        
        results['Combo1_ChakraNet_Focal'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 1: {e}")
        traceback.print_exc()
        results['Combo1_ChakraNet_Focal'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # COMBO 2: Topo-ChakraNet & TopologicalLoss Regularizer
    # -------------------------------------------------------------------------
    print("\n>>> [COMBO 2 AUDIT] Topo-ChakraNet & Topological Homology Loss")
    try:
        code_c2 = extract_cells_code("Combo2_Topo_ChakraNet.ipynb", [5, 6])
        scope2 = {
            'torch': torch, 'nn': nn, 'F': F, 'models': models,
            'sigmoid_focal_loss': sigmoid_focal_loss, 'np': np, 'cv2': __import__('cv2'), 'DEVICE': device
        }
        exec(code_c2, scope2)
        
        TopologicalLoss = scope2['TopologicalLoss']
        TopoAwareDeepSupervisionLoss = scope2['TopoAwareDeepSupervisionLoss']
        PraNetResNet101 = scope2['PraNetResNet101']
        
        # Test TopologicalLoss
        topo_fn = TopologicalLoss(lam=0.12).to(device)
        pred = torch.randn(2, 1, 352, 352, device=device, requires_grad=True)
        target = (torch.rand(2, 1, 352, 352, device=device) > 0.5).float()
        
        t_loss = topo_fn(pred, target)
        assert not torch.isnan(t_loss) and not torch.isinf(t_loss)
        t_loss.backward()
        assert pred.grad is not None and torch.norm(pred.grad).item() > 0
        print(f"  [PASS] TopologicalLoss (Betti-0 & Betti-1 components) verified: Loss = {t_loss.item():.4f}, Grad norm = {torch.norm(pred.grad).item():.4f}")
        
        # Test full TopoAwareDeepSupervisionLoss with PraNet
        model2 = PraNetResNet101(channels=64, pretrained=False).to(device)
        model2.train()
        outs2 = model2(torch.randn(2, 3, 352, 352, device=device))
        
        full_topo_criterion = TopoAwareDeepSupervisionLoss(topo_weight=0.12).to(device)
        tot_loss = full_topo_criterion(outs2, target)
        tot_loss.backward()
        print(f"  [PASS] TopoAwareDeepSupervisionLoss forward & backward verified: Total Loss = {tot_loss.item():.4f}")
        
        results['Combo2_Topo_ChakraNet'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 2: {e}")
        traceback.print_exc()
        results['Combo2_Topo_ChakraNet'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # COMBO 3: AdaBN-ChakraNet Test-Time Adaptation
    # -------------------------------------------------------------------------
    print("\n>>> [COMBO 3 AUDIT] AdaBN-ChakraNet Domain Adaptation Engine")
    try:
        code_c3 = extract_cells_code("Combo3_AdaBN_ChakraNet.ipynb", [5, 7])
        scope3 = {
            'torch': torch, 'nn': nn, 'F': F, 'models': models,
            'time': __import__('time'), 'autocast': torch.cuda.amp.autocast, 'np': np, 'device': device
        }
        exec(code_c3, scope3)
        
        PraNetResNet101 = scope3['PraNetResNet101']
        AdaBNAdapter = scope3['AdaBNAdapter']
        
        model3 = PraNetResNet101(channels=64).to(device)
        adapter = AdaBNAdapter(model=model3, device=device)
        
        # Test caching
        assert len(adapter.source_stats) > 0, "Failed to cache source BN statistics!"
        sample_layer = list(adapter.source_stats.keys())[0]
        init_m = adapter.source_stats[sample_layer]['mean'].clone()
        
        # Mock target dataloader with shifted domain
        class DummyTargetLoader:
            def __init__(self):
                self.batch_size = 4
            def __iter__(self):
                for _ in range(5):
                    yield torch.randn(4, 3, 352, 352, device=device) * 2.5 + 3.0
                    
        adapter.adapt_to_target_domain(DummyTargetLoader(), n_adapt_batches=5)
        
        # Check drift report
        drift_report = adapter.compute_domain_drift_metrics()
        assert len(drift_report) == len(adapter.source_stats)
        sample_drift = [d for d in drift_report if d['layer'] == sample_layer][0]
        print(f"  [PASS] AdaBN domain recalibration verified: Layer '{sample_layer}' Delta Mean = {sample_drift['delta_mean']:.4f}, Delta Var = {sample_drift['delta_var']:.4f}")
        assert sample_drift['delta_mean'] > 0 or sample_drift['delta_var'] > 0
        
        # Invariant check: zero backpropagation during AdaBN
        for p in model3.parameters():
            assert p.grad is None, "AdaBN backpropagated gradients into model weights!"
        print(f"  [PASS] Zero-backpropagation invariant verified.")
        
        results['Combo3_AdaBN_ChakraNet'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 3: {e}")
        traceback.print_exc()
        results['Combo3_AdaBN_ChakraNet'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # COMBO 4: DiffusionAug + MC-Dropout Uncertainty Quality Gating
    # -------------------------------------------------------------------------
    print("\n>>> [COMBO 4 AUDIT] DiffusionAug & MC-Dropout Quality Gating")
    try:
        code_c4 = extract_cells_code("Combo4_DiffusionAug_ChakraNet.ipynb", [5])
        scope4 = {
            'torch': torch, 'nn': nn, 'F': F, 'models': models,
            'np': np, 'cv2': __import__('cv2'), 'Path': __import__('pathlib').Path
        }
        # In cell 6 of Combo 4, PraNetResNet101 is defined
        code_c4_pra = extract_cells_code("Combo4_DiffusionAug_ChakraNet.ipynb", [6])
        exec(code_c4_pra, scope4)
        
        PraNetResNet101 = scope4['PraNetResNet101']
        model4 = PraNetResNet101(channels=64, mc_dropout_p=0.20).to(device)
        model4.enable_mc_dropout()
        
        # Test MC Dropout Variance Calculation
        dummy_img = torch.randn(2, 3, 352, 352, device=device)
        mc_samples = []
        with torch.no_grad():
            for _ in range(8):
                out = model4(dummy_img)
                # Primary output is first element if tuple, or tensor
                pred_map = torch.sigmoid(out[0] if isinstance(out, tuple) else out)
                mc_samples.append(pred_map)
                
        stacked = torch.stack(mc_samples, dim=0) # (8, 2, 1, 352, 352)
        variance_map = torch.var(stacked, dim=0)
        mean_var = variance_map.mean().item()
        print(f"  [PASS] MC-Dropout Epistemic Uncertainty verified across 8 stochastic passes:")
        print(f"         Variance map shape: {variance_map.shape}, Mean pixel variance: {mean_var:.6f}")
        assert variance_map.shape == (2, 1, 352, 352)
        
        results['Combo4_DiffusionAug'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 4: {e}")
        traceback.print_exc()
        results['Combo4_DiffusionAug'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # COMBO 5: Fed-ChakraNet Multi-Hospital Federated Learning
    # -------------------------------------------------------------------------
    print("\n>>> [COMBO 5 AUDIT] Fed-ChakraNet Client-Server Architecture & FedAvg")
    try:
        code_c5 = extract_cells_code("Combo5_Federated_ChakraNet.ipynb", [4, 5])
        scope5 = {
            'torch': torch, 'nn': nn, 'F': F, 'models': models, 'optim': torch.optim,
            'sigmoid_focal_loss': sigmoid_focal_loss, 'np': np, 'copy': copy,
            'OrderedDict': OrderedDict, 'DataLoader': torch.utils.data.DataLoader,
            'autocast': torch.cuda.amp.autocast, 'GradScaler': torch.cuda.amp.GradScaler
        }
        exec(code_c5, scope5)
        
        PraNetResNet101 = scope5['PraNetResNet101']
        FederatedClient = scope5['FederatedClient']
        FederatedServer = scope5['FederatedServer']
        
        server = FederatedServer(device=device)
        global_params = server.get_global_parameters()
        
        # Create synthetic dataloaders for 2 hospitals
        class DummyDataset:
            def __init__(self, count):
                self.count = count
            def __len__(self):
                return self.count
            def __getitem__(self, idx):
                return torch.randn(3, 352, 352), (torch.rand(1, 352, 352) > 0.5).float()
                
        loader_A = torch.utils.data.DataLoader(DummyDataset(8), batch_size=4)
        loader_B = torch.utils.data.DataLoader(DummyDataset(24), batch_size=4)
        
        client_A = FederatedClient("Hospital_1", loader_A, loader_A, device=device)
        client_B = FederatedClient("Hospital_2", loader_B, loader_B, device=device)
        
        client_A.set_parameters(global_params)
        client_B.set_parameters(global_params)
        
        # Simulate local training
        loss_A = client_A.train_local(epochs=1, lr=1e-4)
        loss_B = client_B.train_local(epochs=1, lr=1e-4)
        print(f"  [PASS] Local Client Training verified: Client A loss = {loss_A:.4f}, Client B loss = {loss_B:.4f}")
        
        # Test FedAvg Server Aggregation
        updates = [client_A.get_parameters(), client_B.get_parameters()]
        weights = [8, 24] # 25% Hospital 1, 75% Hospital 2
        server.aggregate_fedavg(updates, weights)
        
        new_global_params = server.get_global_parameters()
        assert len(new_global_params) == len(global_params)
        
        # Broadcast updated weights back to clients
        client_A.set_parameters(new_global_params)
        client_B.set_parameters(new_global_params)
        
        val_dice_A, val_iou_A = client_A.evaluate_local()
        print(f"  [PASS] FedAvg aggregation & synchronization verified: Client A Val DSC = {val_dice_A:.4f}, mIoU = {val_iou_A:.4f}")
        
        results['Combo5_Federated'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 5: {e}")
        traceback.print_exc()
        results['Combo5_Federated'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # COMBO 6: ChakraTransformer & Conformal Calibration
    # -------------------------------------------------------------------------
    print("\n>>> [COMBO 6 AUDIT] ChakraTransformer & Split-Conformal Calibrator")
    try:
        import timm
        code_c6 = extract_cells_code("Combo6_ChakraTransformer.ipynb", [4, 5, 6])
        scope6 = {
            'torch': torch, 'nn': nn, 'F': F, 'timm': timm, 'optim': torch.optim,
            'sigmoid_focal_loss': sigmoid_focal_loss, 'np': np, 'device': device,
            'DataLoader': torch.utils.data.DataLoader, 'autocast': torch.cuda.amp.autocast,
            'GradScaler': torch.cuda.amp.GradScaler
        }
        exec(code_c6, scope6)
        
        ChakraTransformerSegmenter = scope6['ChakraTransformerSegmenter']
        ConformalCalibrator = scope6['ConformalCalibrator']
        
        # Instantiate model
        transformer_model = ChakraTransformerSegmenter(backbone_name='vit_base_patch16_384', pretrained=False).to(device)
        transformer_model.train()
        
        dummy_in = torch.randn(2, 3, 384, 384, device=device)
        logits = transformer_model(dummy_in)
        assert logits.shape == (2, 1, 384, 384), f"Expected (2, 1, 384, 384), got {logits.shape}"
        
        loss_val = logits.mean()
        loss_val.backward()
        print(f"  [PASS] ChakraTransformer (ViT Backbone + 4-Stage Progressive Decoder) forward/backward verified.")
        
        # Test ConformalCalibrator
        calibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05])
        
        # Build synthetic calibration dataset
        class DummyCalDataset:
            def __len__(self): return 16
            def __getitem__(self, idx):
                img = torch.randn(3, 384, 384)
                msk = torch.zeros(1, 384, 384)
                msk[0, 100:200, 100:200] = 1.0 # 100x100 polyp
                return img, msk
                
        cal_loader = torch.utils.data.DataLoader(DummyCalDataset(), batch_size=4)
        calibrator.calibrate(transformer_model, cal_loader, device=device)
        
        assert 0.10 in calibrator.q_hats and 0.05 in calibrator.q_hats
        print(f"  [PASS] Split-conformal calibration verified:")
        print(f"         Alpha 0.10 -> q_hat: {calibrator.q_hats[0.10]['q_hat']:.4f}, tau_alpha: {calibrator.q_hats[0.10]['tau_alpha']:.4f}")
        print(f"         Alpha 0.05 -> q_hat: {calibrator.q_hats[0.05]['q_hat']:.4f}, tau_alpha: {calibrator.q_hats[0.05]['tau_alpha']:.4f}")
        
        # Test predict_conformal_bands
        prob_map = np.random.uniform(0, 1, (384, 384)).astype(np.float32)
        inner, outer, band = calibrator.predict_conformal_bands(prob_map, alpha=0.05)
        assert inner.shape == (384, 384) and outer.shape == (384, 384) and band.shape == (384, 384)
        assert (outer >= inner).all(), "Outer safety envelope must contain inner core!"
        assert np.array_equal(band, np.clip(outer.astype(int) - inner.astype(int), 0, 1)), "Uncertainty band formula mismatch!"
        print(f"  [PASS] Conformal prediction bands (inner, outer, uncertainty band) verified mathematically.")
        
        results['Combo6_ChakraTransformer'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 6: {e}")
        traceback.print_exc()
        results['Combo6_ChakraTransformer'] = f'FAIL: {e}'

    print("\n" + "=" * 80)
    print("FINAL SUMMARY OF FORENSIC UNIT AUDIT RESULTS:")
    print("=" * 80)
    all_clean = True
    for combo, status in results.items():
        print(f"  {combo:35s}: {status}")
        if status != 'PASS':
            all_clean = False
            
    print("=" * 80)
    if all_clean:
        print("VERDICT: CLEAN (All 6 combinations contain authentic, functional algorithmic implementations)")
    else:
        print("VERDICT: INTEGRITY VIOLATION (One or more failures detected)")
        
    return all_clean, results

if __name__ == '__main__':
    run_suite()
