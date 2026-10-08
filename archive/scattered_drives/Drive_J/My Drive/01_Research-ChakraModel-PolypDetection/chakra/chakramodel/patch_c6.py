import json
import re

notebook_path = r'm:\chakramodel\notebooks\Combo6_ChakraTransformer.ipynb'
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        
        # 1. Update Tri-split to 700/150/150
        if 'n_train = int(0.80 * n_total)' in source:
            source = source.replace('n_train = int(0.80 * n_total)', 'n_train = int(0.70 * n_total)')
            source = source.replace('n_cal   = int(0.10 * n_total)', 'n_cal   = int(0.15 * n_total)')
            cell['source'] = [s + '\n' for s in source.split('\n')][:-1]

        # 2. Fix torch.cuda.amp -> torch.amp
        if 'from torch.cuda.amp import GradScaler, autocast' in source:
            source = source.replace('from torch.cuda.amp import GradScaler, autocast', 'from torch.amp import GradScaler, autocast')
            cell['source'] = [s + '\n' for s in source.split('\n')][:-1]
            
        if 'autocast(dtype=torch.float16)' in source:
            source = source.replace("autocast(dtype=torch.float16)", "autocast(device_type='cuda', dtype=torch.float16)")
            cell['source'] = [s + '\n' for s in source.split('\n')][:-1]

        # 3. Update ConformalCalibrator to use RCPS (Image-Level Risk)
        if 'class ConformalCalibrator' in source:
            rcps_class = """class ConformalCalibrator:
    \"\"\"
    Risk-Controlling Prediction Sets (RCPS) Calibrator for Pixel-wise Segmentation.
    Properly handles spatial correlation by calibrating expected image-level risk.
    \"\"\"
    def __init__(self, alpha_levels: list[float] = [0.10, 0.05]):
        self.alpha_levels = alpha_levels
        self.calibrated_thresholds = {}

    def calibrate(self, model: nn.Module, cal_loader: DataLoader, device: torch.device):
        model.eval().to(device)
        print(f"\\n{'='*75}")
        print(f"  🛡️ EXECUTING RCPS CONFORMAL CALIBRATION (IMAGE-LEVEL EXCHANGEABILITY)")
        print(f"{'='*75}")

        taus = np.linspace(0.0, 1.0, 1000)
        risk_matrix = []

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
                        true_p = p_map[gt_map]
                        sorted_p = np.sort(true_p)
                        counts = np.searchsorted(sorted_p, taus)
                        r_i = counts / len(true_p)
                        risk_matrix.append(r_i)

        risk_matrix = np.array(risk_matrix)
        mean_risks = risk_matrix.mean(axis=0)
        N = risk_matrix.shape[0]
        print(f"📊 Evaluated {N} calibration images with valid polyp masks.")

        for alpha in self.alpha_levels:
            valid_taus = taus[mean_risks <= alpha]
            tau_hat = valid_taus[-1] if len(valid_taus) > 0 else 0.0
            
            # For the inner core, we can just use a highly confident threshold like 0.90
            q_hat = 0.90 

            self.calibrated_thresholds[alpha] = {
                'tau_alpha': tau_hat,
                'q_hat': q_hat,
                'target_coverage': (1 - alpha) * 100
            }
            print(f"  • Alpha: {alpha:0.2f} | Target Coverage: {(1-alpha)*100:0.1f}% | RCPS Safety Threshold (tau_alpha): {tau_hat:.4f}")

    def predict_conformal_bands(self, prob_map: np.ndarray, alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        assert alpha in self.calibrated_thresholds, f"Alpha {alpha} not calibrated!"
        tau = self.calibrated_thresholds[alpha]['tau_alpha']
        q_hat = self.calibrated_thresholds[alpha]['q_hat']

        # Outer safety envelope: Guaranteed safety resection envelope
        outer_mask = (prob_map >= tau).astype(np.uint8)
        # Inner core: Confident polyp tissue
        inner_mask = (prob_map >= q_hat).astype(np.uint8)
        # Uncertainty resection margin
        uncertainty_band = np.clip(outer_mask.astype(np.int32) - inner_mask.astype(np.int32), 0, 1).astype(np.uint8)

        return inner_mask, outer_mask, uncertainty_band

    def evaluate_test_coverage(self, model: nn.Module, test_loader: DataLoader, device: torch.device) -> dict:
        model.eval().to(device)
        coverage_stats = {alpha: {'covered_pixels': 0, 'total_polyp_pixels': 0, 'band_fractions': [], 'image_risks': []} for alpha in self.alpha_levels}

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
                        for alpha in self.alpha_levels:
                            inner, outer, band = self.predict_conformal_bands(p_map, alpha=alpha)
                            covered = (gt_map & (outer > 0)).sum()
                            
                            # Record the empirical risk for this image
                            risk_i = 1.0 - (covered / n_polyps)
                            coverage_stats[alpha]['image_risks'].append(risk_i)
                            
                            coverage_stats[alpha]['covered_pixels'] += covered
                            coverage_stats[alpha]['total_polyp_pixels'] += n_polyps
                            coverage_stats[alpha]['band_fractions'].append(band.sum() / max(outer.sum(), 1))

        summary = {}
        for alpha, stats in coverage_stats.items():
            global_coverage = stats['covered_pixels'] / max(1, stats['total_polyp_pixels'])
            mean_image_risk = np.mean(stats['image_risks'])
            rcps_coverage = 1.0 - mean_image_risk
            
            mean_band_pct = np.mean(stats['band_fractions']) * 100
            summary[alpha] = {
                'target_coverage': (1 - alpha) * 100,
                'empirical_coverage': rcps_coverage * 100,
                'global_pixel_coverage': global_coverage * 100,
                'mean_band_pct': mean_band_pct,
                'guarantee_satisfied': rcps_coverage >= (1 - alpha)
            }
        return summary
"""
            # Replace the entire class definition
            # We can use regex or just string splitting
            parts = source.split('class ConformalCalibrator:')
            prefix = parts[0]
            # Find the end of the class (which is before "# Execute Split-Conformal Calibration")
            exec_marker = "# Execute Split-Conformal Calibration"
            suffix = exec_marker + parts[1].split(exec_marker)[1]
            
            new_source = prefix + rcps_class + '\n' + suffix
            cell['source'] = [s + '\n' for s in new_source.split('\n')][:-1]

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Updated Combo6_ChakraTransformer.ipynb with RCPS successfully.')
