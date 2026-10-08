"""
Verification helper to test all 14 adversarial scripts against patched inputs.
Ensures that each script exits 0 when its respective flaw has been resolved.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(r"M:\chakramodel")
ADV_DIR = REPO_ROOT / "tests" / "adversarial"

def test_exit_zero_all():
    print("Testing that all 14 adversarial detection scripts exit 0 when provided patched inputs...")
    results = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        tpath = Path(tmpdir)

        # 1. Patched chakranet_segmenter.py with skip connections
        p1 = tpath / "patched_flaw_01.py"
        p1.write_text("""
import torch
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    def __init__(self):
        super().__init__()
        self.skip_convs = nn.ModuleList([nn.Conv2d(1024, 128, 1)])
        self.up1 = nn.ConvTranspose2d(1024, 256, 4, 4)
    def forward(self, x):
        features = [self.skip_convs[0](x)]
        return features
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_01_no_skip_connections.py"), "--target-file", str(p1)], capture_output=True, text=True)
        results["Flaw 01"] = res.returncode

        # 2. Patched with num_classes=0
        p2 = tpath / "patched_flaw_02.py"
        p2.write_text("""
import timm
class M:
    def __init__(self):
        self.backbone = timm.create_model('vit_large_patch16_384', pretrained=True, num_classes=0)
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_02_dead_imagenet_head.py"), "--target-file", str(p2)], capture_output=True, text=True)
        results["Flaw 02"] = res.returncode

        # 3. Patched with no dead classes
        p3 = tpath / "patched_flaw_03.py"
        p3.write_text("""
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    pass
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_03_dead_code.py"), "--target-file", str(p3)], capture_output=True, text=True)
        results["Flaw 03"] = res.returncode

        # 4. Patched without self.to('cpu') in forward
        p4 = tpath / "patched_flaw_04.py"
        p4.write_text("""
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    def forward(self, x):
        try:
            return x * 2
        except RuntimeError:
            raise
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_04_oom_fallback.py"), "--target-file", str(p4)], capture_output=True, text=True)
        results["Flaw 04"] = res.returncode

        # 5. Patched with use_tta=False default
        p5 = tpath / "patched_flaw_05.py"
        p5.write_text("""
class ChakraNet:
    def __init__(self, use_tta: bool = False):
        self.use_tta = use_tta
    def segment_roi(self):
        tta_active = getattr(self, 'use_tta', False)
        return tta_active
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_05_tta_enabled_by_default.py"), "--target-file", str(p5)], capture_output=True, text=True)
        results["Flaw 05"] = res.returncode

        # 6. Patched torch.load with weights_only=True
        p6 = tpath / "patched_flaw_06.py"
        p6.write_text("""
import torch
sd = torch.load("model.pth", map_location="cpu", weights_only=True)
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_06_unguarded_torch_load.py"), "--target-file", str(p6)], capture_output=True, text=True)
        results["Flaw 06"] = res.returncode

        # 7. Patched load_state_dict raising on missing keys
        p7 = tpath / "patched_flaw_07.py"
        p7.write_text("""
class ChakraNet:
    def load(self, sd):
        missing, unexpected = self.model.load_state_dict(sd, strict=False)
        if missing or unexpected:
            raise RuntimeError("Mismatch!")
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_07_strict_false_state_dict.py"), "--target-file", str(p7)], capture_output=True, text=True)
        results["Flaw 07"] = res.returncode

        # 8. Patched canonical formula
        p8 = tpath / "patched_flaw_08.py"
        p8.write_text("""
score_pos = (1.0 - prob_resized) + variance
score_neg = prob_resized + variance
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_08_conformal_formula_sign.py"), "--target-file", str(p8)], capture_output=True, text=True)
        results["Flaw 08"] = res.returncode

        # 9. Patched MC dropout metrics
        p9 = tpath / "patched_flaw_09.json"
        p9.write_text('{"mean_uncertainty": 0.042}', encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_09_mc_dropout_collapse.py"), "--target-file", str(p9)], capture_output=True, text=True)
        results["Flaw 09"] = res.returncode

        # 10. Patched reconciled calibration metrics
        p10_c = tpath / "calib.json"
        p10_c.write_text('{"q_hat_pos": 0.521484375}', encoding="utf-8")
        p10_m = tpath / "metrics.json"
        p10_m.write_text('{"conformal_status": "DEPRECATED_SUPERSEDED: Replaced by canonical calibration"}', encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_10_contradictory_calibration_qhat.py"), "--calib-file", str(p10_c), "--metrics-file", str(p10_m)], capture_output=True, text=True)
        results["Flaw 10"] = res.returncode

        # 11. Patched requirements pinned
        p11 = tpath / "requirements.txt"
        p11.write_text("torch==2.1.2\ntimm==0.9.12\nnumpy==1.24.3\n", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_11_unpinned_dependencies.py"), "--target-file", str(p11)], capture_output=True, text=True)
        results["Flaw 11"] = res.returncode

        # 12. Patched CI workflow with src/ lint and pytest
        p12 = tpath / "test.yml"
        p12.write_text("""
jobs:
  lint:
    steps:
      - run: flake8 src/ tests/
  test:
    steps:
      - run: pytest tests/
""", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_12_ci_lacking_src_coverage.py"), "--target-file", str(p12)], capture_output=True, text=True)
        results["Flaw 12"] = res.returncode

        # 13. Patched provenance document
        p13_doc = tpath / "TRAINING_PROVENANCE.md"
        p13_doc.write_text("Reconciles 2376 batches and caveats zero-shot generalization.", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_13_unrecoverable_training_batches.py"), "--doc-file", str(p13_doc)], capture_output=True, text=True)
        results["Flaw 13"] = res.returncode

        # 14. Patched FIXES.md and HONEST_METRICS.md
        p14_fixes = tpath / "FIXES.md"
        p14_fixes.write_text("Mean DSC: 0.8023", encoding="utf-8")
        p14_honest = tpath / "HONEST_METRICS.md"
        p14_honest.write_text("Retracted metrics: 0.7304 unsubstantiated.", encoding="utf-8")
        res = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_14_headline_metric_artifact_absence.py"), "--target-file", str(p14_fixes), "--honest-metrics", str(p14_honest)], capture_output=True, text=True)
        results["Flaw 14"] = res.returncode

    print("Results on patched inputs:")
    all_zero = True
    for fid, code in results.items():
        print(f"  {fid}: Exit {code} {'(PASS)' if code == 0 else '(FAIL)'}")
        if code != 0:
            all_zero = False

    if all_zero:
        print("\nAll 14 scripts correctly exit 0 when provided patched inputs!")
        sys.exit(0)
    else:
        print("\nSome scripts did not exit 0 on patched inputs.")
        sys.exit(1)

if __name__ == "__main__":
    test_exit_zero_all()
