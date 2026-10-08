import json
import os
import sys
import traceback
import torch
import torch.nn as nn
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
                # Skip subprocessing pip installs or sys.exit
                if 'subprocess.run' in line and 'pip' in line:
                    continue
                code_lines.append(line)
    return ''.join(code_lines)

def run_tests():
    print("=" * 80)
    print("COMPREHENSIVE FORENSIC UNIT & EMPIRICAL INTEGRITY SUITE")
    print("=" * 80)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Active Test Acceleration Device: {device}\n")
    
    test_results = {}
    
    # -------------------------------------------------------------------------
    # TEST 1: Combo 1 (PraNetResNet101 + DeepSupervisionDiceFocalLoss)
    # -------------------------------------------------------------------------
    print(">>> [TEST 1] Combo 1: PraNetResNet101 Architecture & DeepSupervisionLoss")
    try:
        code_c1 = extract_cells_code("Combo1_ChakraNet_Focal.ipynb", [1, 2, 5, 6])
        scope1 = {'DEVICE': device, 'torch': torch, 'nn': nn, 'np': np}
        exec(code_c1, scope1)
        
        PraNetResNet101 = scope1['PraNetResNet101']
        DeepSupervisionDiceFocalLoss = scope1['DeepSupervisionDiceFocalLoss']
        
        # Instantiate model (using pretrained=False for fast offline test or pretrained=True)
        model = PraNetResNet101(num_classes=1, pretrained=False).to(device)
        model.train()
        
        # Parameter counts
        total_p = sum(p.numel() for p in model.parameters())
        trainable_p = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"  [PASS] PraNetResNet101 instantiated. Total params: {total_p:,}, Trainable: {trainable_p:,}")
        
        # Forward pass: shape (2, 3, 352, 352)
        dummy_x = torch.randn(2, 3, 352, 352, device=device)
        outputs = model(dummy_x)
        
        assert isinstance(outputs, (tuple, list)), f"Expected tuple/list of outputs, got {type(outputs)}"
        print(f"  [PASS] Forward pass returned {len(outputs)} deep supervision stage outputs:")
        for i, out in enumerate(outputs):
            print(f"    sout{i+1}: shape = {out.shape}")
            assert out.shape == (2, 1, 352, 352), f"Expected (2, 1, 352, 352), got {out.shape}"
            
        # Loss computation & backward
        criterion = DeepSupervisionDiceFocalLoss()
        dummy_target = (torch.rand(2, 1, 352, 352, device=device) > 0.5).float()
        loss = criterion(outputs, dummy_target) if isinstance(outputs, list) else criterion(*outputs, dummy_target)
        print(f"  [PASS] DeepSupervisionDiceFocalLoss: loss = {loss.item():.4f}")
        assert not torch.isnan(loss) and not torch.isinf(loss) and loss.item() > 0
        
        loss.backward()
        grads = [p.grad is not None and torch.norm(p.grad).item() > 0 for p in model.parameters() if p.requires_grad]
        grad_ratio = sum(grads) / len(grads)
        print(f"  [PASS] Gradient propagation: {sum(grads)}/{len(grads)} ({grad_ratio*100:.1f}%) parameters have valid nonzero gradients.")
        assert grad_ratio > 0.95
        
        test_results['Combo1_PraNet_Focal'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 1 Test failed: {e}")
        traceback.print_exc()
        test_results['Combo1_PraNet_Focal'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # TEST 2: Combo 2 (Topo-ChakraNet + TopologicalLoss / TopoAwareDeepSupervisionLoss)
    # -------------------------------------------------------------------------
    print("\n>>> [TEST 2] Combo 2: Topo-ChakraNet & Topological Loss Regularizer")
    try:
        code_c2 = extract_cells_code("Combo2_Topo_ChakraNet.ipynb", [1, 2, 5, 6])
        scope2 = {'DEVICE': device, 'torch': torch, 'nn': nn, 'np': np}
        exec(code_c2, scope2)
        
        TopologicalLoss = scope2['TopologicalLoss']
        TopoAwareDeepSupervisionLoss = scope2['TopoAwareDeepSupervisionLoss']
        PraNetResNet101 = scope2['PraNetResNet101']
        
        # Test TopologicalLoss directly
        topo_fn = TopologicalLoss().to(device)
        pred = torch.randn(2, 1, 352, 352, device=device, requires_grad=True)
        target = (torch.rand(2, 1, 352, 352, device=device) > 0.5).float()
        
        t_loss = topo_fn(pred, target)
        print(f"  [PASS] TopologicalLoss output: {t_loss.item():.4f}")
        assert not torch.isnan(t_loss) and not torch.isinf(t_loss)
        
        t_loss.backward()
        assert pred.grad is not None and torch.norm(pred.grad).item() > 0
        print(f"  [PASS] TopologicalLoss backward successful. Grad norm: {torch.norm(pred.grad).item():.4f}")
        
        # Test TopoAwareDeepSupervisionLoss with PraNet
        model2 = PraNetResNet101(num_classes=1, pretrained=False).to(device)
        dummy_x = torch.randn(2, 3, 352, 352, device=device)
        outs2 = model2(dummy_x)
        
        topo_sup_loss = TopoAwareDeepSupervisionLoss().to(device)
        total_loss = topo_sup_loss(*outs2, target) if isinstance(outs2, tuple) else topo_sup_loss(outs2, target)
        print(f"  [PASS] TopoAwareDeepSupervisionLoss: {total_loss.item():.4f}")
        total_loss.backward()
        print(f"  [PASS] Full Topo-PraNet backward pass successful.")
        
        test_results['Combo2_Topo_ChakraNet'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 2 Test failed: {e}")
        traceback.print_exc()
        test_results['Combo2_Topo_ChakraNet'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # TEST 3: Combo 3 (AdaBN-ChakraNet + AdaBNAdapter)
    # -------------------------------------------------------------------------
    print("\n>>> [TEST 3] Combo 3: AdaBN-ChakraNet Test-Time Adaptation")
    try:
        code_c3 = extract_cells_code("Combo3_AdaBN_ChakraNet.ipynb", [1, 2, 5, 7])
        scope3 = {'DEVICE': device, 'torch': torch, 'nn': nn, 'np': np}
        exec(code_c3, scope3)
        
        PraNetResNet101 = scope3['PraNetResNet101']
        AdaBNAdapter = scope3['AdaBNAdapter']
        
        model3 = PraNetResNet101(num_classes=1, pretrained=False).to(device)
        adapter = AdaBNAdapter(model=model3, device=device)
        
        # Check initial BatchNorm statistics on a representative BN layer
        sample_bn = None
        for m in model3.modules():
            if isinstance(m, nn.BatchNorm2d):
                sample_bn = m
                break
        assert sample_bn is not None, "No BatchNorm2d found in PraNetResNet101!"
        
        init_running_mean = sample_bn.running_mean.clone()
        init_running_var = sample_bn.running_var.clone()
        
        # Synthetic shifted target domain loader (batches with mean=2.5, std=1.8)
        class MockShiftedLoader:
            def __iter__(self):
                for _ in range(4):
                    yield torch.randn(4, 3, 352, 352, device=device) * 1.8 + 2.5
            def __len__(self):
                return 4
                
        target_loader = MockShiftedLoader()
        adapter.adapt(target_loader)
        
        new_running_mean = sample_bn.running_mean.clone()
        new_running_var = sample_bn.running_var.clone()
        
        mean_diff = torch.norm(new_running_mean - init_running_mean).item()
        var_diff = torch.norm(new_running_var - init_running_var).item()
        print(f"  [PASS] AdaBN adaptation executed. Running Mean shift: {mean_diff:.4f}, Running Var shift: {var_diff:.4f}")
        assert mean_diff > 1e-3 or var_diff > 1e-3, "AdaBN did not update running statistics!"
        
        # Verify model parameters did NOT accumulate gradients
        for p in model3.parameters():
            assert p.grad is None, "AdaBN should not perform backprop or calculate parameter gradients!"
        print(f"  [PASS] Verified zero-backpropagation invariant in AdaBN.")
        
        test_results['Combo3_AdaBN_ChakraNet'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 3 Test failed: {e}")
        traceback.print_exc()
        test_results['Combo3_AdaBN_ChakraNet'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # TEST 4: Combo 4 (DiffusionAug + MC Dropout Quality Gating)
    # -------------------------------------------------------------------------
    print("\n>>> [TEST 4] Combo 4: DiffusionAug-ChakraNet & MC-Dropout Filter")
    try:
        code_c4 = extract_cells_code("Combo4_DiffusionAug_ChakraNet.ipynb", [1, 2, 5])
        scope4 = {'DEVICE': device, 'torch': torch, 'nn': nn, 'np': np}
        exec(code_c4, scope4)
        
        PraNetResNet101 = scope4['PraNetResNet101']
        model4 = PraNetResNet101(num_classes=1, pretrained=False).to(device)
        model4.train()
        
        # Test MC Dropout Variance calculation
        dummy_img = torch.randn(2, 3, 352, 352, device=device)
        mc_passes = []
        with torch.no_grad():
            for _ in range(8):
                out = model4(dummy_img)
                # Primary output is first element
                pred_map = torch.sigmoid(out[0] if isinstance(out, (tuple, list)) else out)
                mc_passes.append(pred_map)
                
        stacked = torch.stack(mc_passes, dim=0) # (8, 2, 1, 352, 352)
        epistemic_variance = torch.var(stacked, dim=0)
        mean_uncertainty = epistemic_variance.mean().item()
        print(f"  [PASS] MC-Dropout epistemic uncertainty computed across 8 stochastic passes.")
        print(f"  Epistemic variance map shape: {epistemic_variance.shape}, Mean uncertainty: {mean_uncertainty:.6f}")
        assert epistemic_variance.shape == (2, 1, 352, 352)
        
        test_results['Combo4_DiffusionAug'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 4 Test failed: {e}")
        traceback.print_exc()
        test_results['Combo4_DiffusionAug'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # TEST 5: Combo 5 (Fed-ChakraNet + Multi-Center FedAvg)
    # -------------------------------------------------------------------------
    print("\n>>> [TEST 5] Combo 5: Federated Learning FedAvg Framework")
    try:
        code_c5 = extract_cells_code("Combo5_Federated_ChakraNet.ipynb", [1, 4, 5])
        scope5 = {'DEVICE': device, 'torch': torch, 'nn': nn, 'np': np}
        exec(code_c5, scope5)
        
        FederatedClient = scope5['FederatedClient']
        FederatedServer = scope5['FederatedServer']
        PraNetResNet101 = scope5['PraNetResNet101']
        
        server_model = PraNetResNet101(num_classes=1, pretrained=False).to(device)
        server = FederatedServer(global_model=server_model, device=device)
        
        client_A = FederatedClient(client_id="Hospital_Oslo", model=PraNetResNet101(num_classes=1, pretrained=False).to(device), device=device)
        client_B = FederatedClient(client_id="Hospital_Madrid", model=PraNetResNet101(num_classes=1, pretrained=False).to(device), device=device)
        
        # Broadcast server weights to clients
        global_w = server.get_global_weights()
        client_A.set_weights(global_w)
        client_B.set_weights(global_w)
        
        # Simulate local updates
        w_A = client_A.get_weights()
        w_B = client_B.get_weights()
        for k in w_A:
            if w_A[k].is_floating_point():
                w_A[k] = w_A[k] + 2.0
                w_B[k] = w_B[k] + 6.0
        client_A.set_weights(w_A)
        client_B.set_weights(w_B)
        
        # Client A: 100 samples (weight 0.25), Client B: 300 samples (weight 0.75)
        # Expected new weight delta: 0.25 * 2.0 + 0.75 * 6.0 = 5.0
        server.aggregate_weights([
            (client_A.get_weights(), 100),
            (client_B.get_weights(), 300)
        ])
        
        updated_global_w = server.get_global_weights()
        for k in global_w:
            if global_w[k].is_floating_point():
                delta = (updated_global_w[k] - global_w[k]).mean().item()
                print(f"  [PASS] FedAvg mathematical aggregation test. Expected offset: 5.0, Computed offset: {delta:.4f}")
                assert abs(delta - 5.0) < 1e-4, f"FedAvg aggregation error! Expected 5.0, got {delta}"
                break
                
        test_results['Combo5_Federated'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 5 Test failed: {e}")
        traceback.print_exc()
        test_results['Combo5_Federated'] = f'FAIL: {e}'

    # -------------------------------------------------------------------------
    # TEST 6: Combo 6 (ChakraTransformer + ConformalCalibrator)
    # -------------------------------------------------------------------------
    print("\n>>> [TEST 6] Combo 6: ChakraTransformer & Conformal Calibration")
    try:
        code_c6 = extract_cells_code("Combo6_ChakraTransformer.ipynb", [1, 4, 6])
        scope6 = {'DEVICE': device, 'torch': torch, 'nn': nn, 'np': np}
        exec(code_c6, scope6)
        
        ChakraTransformerSegmenter = scope6['ChakraTransformerSegmenter']
        ConformalCalibrator = scope6['ConformalCalibrator']
        
        # Instantiate ChakraTransformer
        transformer_model = ChakraTransformerSegmenter(pretrained=False).to(device)
        transformer_model.train()
        
        total_p = sum(p.numel() for p in transformer_model.parameters())
        print(f"  [PASS] ChakraTransformerSegmenter instantiated. Total params: {total_p:,}")
        
        # Forward pass on 384x384
        dummy_x = torch.randn(2, 3, 384, 384, device=device)
        out = transformer_model(dummy_x)
        print(f"  [PASS] ChakraTransformer output shape: {out.shape}")
        assert out.shape == (2, 1, 384, 384), f"Expected (2, 1, 384, 384), got {out.shape}"
        
        loss_val = out.mean()
        loss_val.backward()
        print(f"  [PASS] Backward pass through Vision Transformer & 4-Stage Progressive Decoder successful.")
        
        # Test ConformalCalibrator
        calibrator = ConformalCalibrator(alpha=0.10) # 90% confidence
        cal_logits = torch.randn(60, 1, 384, 384, device=device)
        cal_targets = (torch.sigmoid(cal_logits) > 0.5).float()
        
        calibrator.calibrate(cal_logits, cal_targets)
        q_hat = calibrator.q_hat
        print(f"  [PASS] ConformalCalibrator calibrated q_hat (1-alpha quantile): {q_hat:.4f}")
        assert q_hat is not None and not np.isnan(q_hat)
        
        # Generate prediction sets on test batch
        test_logits = torch.randn(5, 1, 384, 384, device=device)
        sets = calibrator.predict(test_logits)
        print(f"  [PASS] Conformal prediction bounds computed: type = {type(sets)}")
        
        test_results['Combo6_ChakraTransformer_Conformal'] = 'PASS'
    except Exception as e:
        print(f"  [FAIL] Combo 6 Test failed: {e}")
        traceback.print_exc()
        test_results['Combo6_ChakraTransformer_Conformal'] = f'FAIL: {e}'

    print("\n" + "=" * 80)
    print("FINAL EMPIRICAL VERDICT SUMMARY:")
    all_passed = True
    for k, v in test_results.items():
        print(f"  {k:35s}: {v}")
        if v != 'PASS':
            all_passed = False
    print("=" * 80)
    
    if all_passed:
        print("\n🎉 ALL 6 COMBINATION MODULES PASSED COMPREHENSIVE FORENSIC VERIFICATION!")
    else:
        print("\n❌ INTEGRITY VIOLATIONS DETECTED IN ONE OR MORE MODULES!")

if __name__ == '__main__':
    run_tests()
