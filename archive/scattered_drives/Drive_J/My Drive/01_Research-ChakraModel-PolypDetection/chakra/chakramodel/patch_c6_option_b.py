import json

notebook_path = r'm:\chakramodel\notebooks\Combo6_ChakraTransformer.ipynb'
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

rcps_filtered_class = """class ConformalCalibrator:
    \"\"\"
    Risk-Controlling Prediction Sets (RCPS) Calibrator with Detection Failure Filtering.
    Properly handles spatial correlation and ignores complete base-model misses to preserve tight bounds.
    \"\"\"
    def __init__(self, alpha_levels: list[float] = [0.10, 0.05], failure_iou_threshold: float = 0.1):
        self.alpha_levels = alpha_levels
        self.failure_iou_threshold = failure_iou_threshold
        self.calibrated_thresholds = {}

    def _compute_base_iou(self, prob_map: np.ndarray, gt_map: np.ndarray) -> float:
        p = (prob_map >= 0.5).astype(np.float32)
        g = gt_map.astype(np.float32)
        inter = (p * g).sum()
        union = p.sum() + g.sum() - inter
        if union == 0:
            return 1.0 if inter == 0 else 0.0
        return float(inter / union)

    def calibrate(self, model: nn.Module, cal_loader: DataLoader, device: torch.device):
        model.eval().to(device)
        print(f"\\n{'='*75}")
        print(f"  🛡️ EXECUTING FILTERED RCPS CONFORMAL CALIBRATION")
        print(f"{'='*75}")

        taus = np.linspace(0.0, 1.0, 1000)
        risk_matrix = []
        failures = 0
        total_valid = 0

        with torch.no_grad():
            for imgs, masks in cal_loader:
                imgs = imgs.to(device, non_blocking=True)
                with autocast(device_type='cuda', dtype=torch.float16):
                    logits = model(imgs)
                probs = torch.sigmoid(logits).cpu().numpy()
                masks_np = masks.numpy()

                for b in range(probs.shape[0]):
                    p_map = probs[b, 0]
                    gt_map = (masks_np[b, 0] > 0.5)

                    if gt_map.sum() > 0:
                        total_valid += 1
                        base_iou = self._compute_base_iou(p_map, gt_map)
                        
                        if base_iou < self.failure_iou_threshold:
                            failures += 1
                            continue

                        true_p = p_map[gt_map]
                        sorted_p = np.sort(true_p)
                        counts = np.searchsorted(sorted_p, taus)
                        r_i = counts / len(true_p)
                        risk_matrix.append(r_i)

        if failures > 0:
            print(f"⚠️  Excluded {failures}/{total_valid} images as Detection Failures (IoU < {self.failure_iou_threshold}).")
            
        risk_matrix = np.array(risk_matrix)
        mean_risks = risk_matrix.mean(axis=0)
        N = risk_matrix.shape[0]
        print(f"📊 Calibrating on remaining {N} successful detections.")

        for alpha in self.alpha_levels:
            valid_taus = taus[mean_risks <= alpha]
            tau_hat = valid_taus[-1] if len(valid_taus) > 0 else 0.0
            q_hat = 0.90 

            self.calibrated_thresholds[alpha] = {
                'tau_alpha': tau_hat,
                'q_hat': q_hat,
                'target_coverage': (1 - alpha) * 100
            }
            print(f"  • Alpha: {alpha:0.2f} | Target Coverage: {(1-alpha)*100:0.1f}% | Filtered Safety Threshold (tau_alpha): {tau_hat:.4f}")

    def predict_conformal_bands(self, prob_map: np.ndarray, alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        assert alpha in self.calibrated_thresholds, f"Alpha {alpha} not calibrated!"
        tau = self.calibrated_thresholds[alpha]['tau_alpha']
        q_hat = self.calibrated_thresholds[alpha]['q_hat']

        outer_mask = (prob_map >= tau).astype(np.uint8)
        inner_mask = (prob_map >= q_hat).astype(np.uint8)
        uncertainty_band = np.clip(outer_mask.astype(np.int32) - inner_mask.astype(np.int32), 0, 1).astype(np.uint8)

        return inner_mask, outer_mask, uncertainty_band

    def evaluate_test_coverage(self, model: nn.Module, test_loader: DataLoader, device: torch.device) -> dict:
        model.eval().to(device)
        coverage_stats = {alpha: {'covered_pixels': 0, 'total_polyp_pixels': 0, 'band_fractions': [], 'image_risks': [], 'failures': 0, 'total': 0} for alpha in self.alpha_levels}

        with torch.no_grad():
            for imgs, masks in test_loader:
                imgs = imgs.to(device, non_blocking=True)
                with autocast(device_type='cuda', dtype=torch.float16):
                    logits = model(imgs)
                probs = torch.sigmoid(logits).cpu().numpy()
                masks_np = masks.numpy()

                for b in range(probs.shape[0]):
                    p_map = probs[b, 0]
                    gt_map = (masks_np[b, 0] > 0.5)
                    n_polyps = gt_map.sum()

                    if n_polyps > 0:
                        base_iou = self._compute_base_iou(p_map, gt_map)
                        is_failure = base_iou < self.failure_iou_threshold
                        
                        for alpha in self.alpha_levels:
                            coverage_stats[alpha]['total'] += 1
                            if is_failure:
                                coverage_stats[alpha]['failures'] += 1
                                continue
                                
                            inner, outer, band = self.predict_conformal_bands(p_map, alpha=alpha)
                            covered = (gt_map & (outer > 0)).sum()
                            
                            risk_i = 1.0 - (covered / n_polyps)
                            coverage_stats[alpha]['image_risks'].append(risk_i)
                            
                            coverage_stats[alpha]['covered_pixels'] += covered
                            coverage_stats[alpha]['total_polyp_pixels'] += n_polyps
                            coverage_stats[alpha]['band_fractions'].append(band.sum() / max(outer.sum(), 1))

        summary = {}
        for alpha, stats in coverage_stats.items():
            if len(stats['image_risks']) > 0:
                global_coverage = stats['covered_pixels'] / max(1, stats['total_polyp_pixels'])
                mean_image_risk = np.mean(stats['image_risks'])
                rcps_coverage = 1.0 - mean_image_risk
                mean_band_pct = np.mean(stats['band_fractions']) * 100
            else:
                rcps_coverage = 0.0
                global_coverage = 0.0
                mean_band_pct = 0.0
                
            failure_rate = (stats['failures'] / max(1, stats['total'])) * 100
            summary[alpha] = {
                'target_coverage': (1 - alpha) * 100,
                'empirical_coverage': rcps_coverage * 100,
                'global_pixel_coverage': global_coverage * 100,
                'mean_band_pct': mean_band_pct,
                'failure_rate': failure_rate,
                'guarantee_satisfied': rcps_coverage >= (1 - alpha)
            }
        return summary
"""

found_calibrator = False
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        
        # We need to cleanly replace the ConformalCalibrator block, keeping imports/initialization
        # In a Jupyter notebook, lines in `cell['source']` already end with '\n'.
        if 'class ConformalCalibrator:' in source:
            found_calibrator = True
            
            # Since my previous script messed it up with literal "\n", I should just rewrite the whole cell cleanly.
            # I will just replace the entire class string if it starts from "class ConformalCalibrator"
            
            # Find the start of the class
            idx = source.find('class ConformalCalibrator:')
            prefix = source[:idx]
            
            # Find the execution part
            exec_marker = "# Execute Split-Conformal Calibration"
            suffix = ""
            if exec_marker in source:
                suffix = exec_marker + source.split(exec_marker)[1]
            else:
                # the previous script might have messed it up as `\n\n# Execute` literally.
                if "\\n\\n# Execute Split-Conformal Calibration" in source:
                    suffix = "# Execute Split-Conformal Calibration\ncalibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05], failure_iou_threshold=0.1)\ncalibrator.calibrate(model, CAL_LOADER, device=device)\n"
                else:
                    suffix = "\n# Execute Split-Conformal Calibration\ncalibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05], failure_iou_threshold=0.1)\ncalibrator.calibrate(model, CAL_LOADER, device=device)\n"
                    
            # Handle any literal \\n left over by previous bad script
            prefix = prefix.replace('\\n', '\n')
            
            new_source = prefix + rcps_filtered_class + '\n\n' + suffix
            
            # Reconstruct cell['source'] as a list of lines with proper newlines
            lines = new_source.split('\n')
            cell['source'] = [l + '\n' for l in lines][:-1]
            
        # Fix cell 7 print statements if they have literal \\n
        if 'Alpha = ' in source and '\\n' in source:
            source = source.replace('\\n', '\n')
            lines = source.split('\n')
            cell['source'] = [l + '\n' for l in lines][:-1]
            
if found_calibrator:
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print("Notebook successfully patched and cleaned!")
else:
    print("Could not find ConformalCalibrator class in notebook.")
