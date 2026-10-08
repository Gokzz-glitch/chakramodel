"""
Test edge cases specified by Reviewer 1 for Flaws 04, 05, 06, and 07.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ADV_DIR = Path(r"M:\chakramodel\tests\adversarial")

def run(cmd):
    res = subprocess.run([sys.executable] + cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def main():
    print("=== Testing Flaws 04, 05, 06, 07 Specific Edge Cases ===")
    all_ok = True

    with tempfile.TemporaryDirectory() as tmpdir:
        t = Path(tmpdir)

        # Edge Case 1: Flaw 04 - Tensor .to('cpu') must not be flagged
        f4_tensor = t / "f4_tensor.py"
        f4_tensor.write_text("""
import torch.nn as nn
class M(nn.Module):
    def forward(self, x):
        logits = x.to('cpu')
        return logits.to('cpu')
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_04_oom_fallback.py"), "--target-file", str(f4_tensor)])
        print(f"Flaw 04 tensor .to('cpu'): exit {code} (expected 0)")
        if code != 0:
            all_ok = False

        f4_self = t / "f4_self.py"
        f4_self.write_text("""
import torch.nn as nn
class M(nn.Module):
    def forward(self, x):
        try:
            return x
        except RuntimeError:
            self.to('cpu')
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_04_oom_fallback.py"), "--target-file", str(f4_self)])
        print(f"Flaw 04 self.to('cpu'): exit {code} (expected 1)")
        if code != 1:
            all_ok = False

        # Edge Case 2: Flaw 05 - Keyword-only argument use_tta: bool = False
        f5_kwonly = t / "f5_kwonly.py"
        f5_kwonly.write_text("""
class ChakraNet:
    def __init__(self, *, use_tta: bool = False):
        self.use_tta = use_tta
    def segment_roi(self):
        return getattr(self, 'use_tta', False)
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_05_tta_enabled_by_default.py"), "--target-file", str(f5_kwonly)])
        print(f"Flaw 05 kwonly use_tta=False: exit {code} (expected 0)")
        if code != 0:
            all_ok = False

        f5_kwonly_true = t / "f5_kwonly_true.py"
        f5_kwonly_true.write_text("""
class ChakraNet:
    def __init__(self, *, use_tta: bool = True):
        self.use_tta = use_tta
    def segment_roi(self):
        return getattr(self, 'use_tta', False)
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_05_tta_enabled_by_default.py"), "--target-file", str(f5_kwonly_true)])
        print(f"Flaw 05 kwonly use_tta=True: exit {code} (expected 1)")
        if code != 1:
            all_ok = False

        # Edge Case 3: Flaw 06 - from torch import load; load(...) detection and malformed exit 2
        f6_direct_unsafe = t / "f6_direct_unsafe.py"
        f6_direct_unsafe.write_text("""
from torch import load
sd = load("model.pth", map_location="cpu")
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_06_unguarded_torch_load.py"), "--target-file", str(f6_direct_unsafe)])
        print(f"Flaw 06 direct import unsafe: exit {code} (expected 1)")
        if code != 1:
            all_ok = False

        f6_direct_safe = t / "f6_direct_safe.py"
        f6_direct_safe.write_text("""
from torch import load
sd = load("model.pth", map_location="cpu", weights_only=True)
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_06_unguarded_torch_load.py"), "--target-file", str(f6_direct_safe)])
        print(f"Flaw 06 direct import safe: exit {code} (expected 0)")
        if code != 0:
            all_ok = False

        f6_malformed = t / "f6_malformed.py"
        f6_malformed.write_text("def invalid syntax ((( :::", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_06_unguarded_torch_load.py"), "--target-file", str(f6_malformed)])
        print(f"Flaw 06 malformed syntax: exit {code} (expected 2)")
        if code != 2:
            all_ok = False

        # Edge Case 4: Flaw 07 - Scoped check prevents unrelated function bypass
        f7_unrelated_bypass = t / "f7_unrelated_bypass.py"
        f7_unrelated_bypass.write_text("""
def check_filename(filename):
    if 'missing' in filename:
        raise ValueError("Missing file")

class ChakraNet:
    def load(self, sd):
        self.net.load_state_dict(sd, strict=False)
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_07_strict_false_state_dict.py"), "--target-file", str(f7_unrelated_bypass)])
        print(f"Flaw 07 unrelated function bypass attempt: exit {code} (expected 1)")
        if code != 1:
            all_ok = False

        f7_scoped_safe = t / "f7_scoped_safe.py"
        f7_scoped_safe.write_text("""
class ChakraNet:
    def load(self, sd):
        m, u = self.net.load_state_dict(sd, strict=False)
        if m or u:
            raise RuntimeError("Key mismatch!")
""", encoding="utf-8")
        code, out, _ = run([str(ADV_DIR / "test_flaw_07_strict_false_state_dict.py"), "--target-file", str(f7_scoped_safe)])
        print(f"Flaw 07 properly scoped guard: exit {code} (expected 0)")
        if code != 0:
            all_ok = False

    print(f"\nALL EDGE CASES RESULT: {'PASS' if all_ok else 'FAIL'}")
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
