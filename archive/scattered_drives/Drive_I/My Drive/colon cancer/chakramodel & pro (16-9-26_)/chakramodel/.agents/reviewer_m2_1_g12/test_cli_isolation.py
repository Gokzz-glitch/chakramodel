"""
Adversarial Review CLI and Isolation Stress-Test
Tests each of the 7 flaw detection scripts with:
1. --help flag (exit code 0)
2. Non-existent file path via --target-file (exit code 2)
3. Malformed / non-Python file via --target-file (exit code 2)
4. Isolated mock file with flaw (exit code 1)
5. Isolated mock file without flaw (exit code 0)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(r"M:\chakramodel")
ADV_DIR = REPO_ROOT / "tests" / "adversarial"

scripts = [
    "test_flaw_01_no_skip_connections.py",
    "test_flaw_02_dead_imagenet_head.py",
    "test_flaw_03_dead_code.py",
    "test_flaw_04_oom_fallback.py",
    "test_flaw_05_tta_enabled_by_default.py",
    "test_flaw_06_unguarded_torch_load.py",
    "test_flaw_07_strict_false_state_dict.py",
]

def run_cmd(args):
    res = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def run_tests():
    print("=== STARTING CLI AND ISOLATION AUDIT FOR FLAWS 01-07 ===")
    overall_pass = True

    with tempfile.TemporaryDirectory() as tmpdir:
        tpath = Path(tmpdir)
        non_existent = tpath / "does_not_exist.py"
        malformed = tpath / "malformed.py"
        malformed.write_text("def invalid syntax ::: ((((", encoding="utf-8")

        for sname in scripts:
            spath = ADV_DIR / sname
            print(f"\nAuditing {sname}:")

            # 1. --help
            code, out, err = run_cmd([str(spath), "--help"])
            if code != 0:
                print(f"  [FAIL] --help returned {code}")
                overall_pass = False
            else:
                print("  [PASS] --help returned 0")

            # 2. Non-existent file via --target-file
            code, out, err = run_cmd([str(spath), "--target-file", str(non_existent)])
            if code != 2:
                print(f"  [FAIL] Non-existent file expected returncode 2, got {code}")
                overall_pass = False
            else:
                print("  [PASS] Non-existent file correctly returned 2")

            # 3. Malformed syntax via --target-file
            code, out, err = run_cmd([str(spath), "--target-file", str(malformed)])
            if code != 2:
                print(f"  [FAIL] Malformed syntax expected returncode 2, got {code}")
                overall_pass = False
            else:
                print("  [PASS] Malformed syntax correctly returned 2")

        # Now test Flaw 01 isolated mock flaw vs patched
        print("\nTesting Flaw 01 isolated mock:")
        flawed_01 = tpath / "flawed_01.py"
        flawed_01.write_text("""
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    def __init__(self):
        super().__init__()
        self.decode_head = nn.Sequential(nn.ConvTranspose2d(1024, 256, 4, 4))
    def forward(self, x):
        return self.decode_head(x)
""", encoding="utf-8")
        patched_01 = tpath / "patched_01.py"
        patched_01.write_text("""
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    def __init__(self):
        super().__init__()
        self.skip_convs = nn.ModuleList([nn.Conv2d(1024, 128, 1)])
    def forward(self, x):
        return self.skip_convs[0](x)
""", encoding="utf-8")
        c1_flaw, _, _ = run_cmd([str(ADV_DIR / "test_flaw_01_no_skip_connections.py"), "--target-file", str(flawed_01)])
        c1_patch, _, _ = run_cmd([str(ADV_DIR / "test_flaw_01_no_skip_connections.py"), "--target-file", str(patched_01)])
        print(f"  Flawed 01: exit {c1_flaw} (expected 1), Patched 01: exit {c1_patch} (expected 0)")
        if c1_flaw != 1 or c1_patch != 0:
            overall_pass = False

        # Flaw 02 isolated mock flaw vs patched
        print("\nTesting Flaw 02 isolated mock:")
        flawed_02 = tpath / "flawed_02.py"
        flawed_02.write_text("""
import timm
class M:
    def __init__(self):
        self.backbone = timm.create_model('vit_large_patch16_384', pretrained=True)
""", encoding="utf-8")
        patched_02 = tpath / "patched_02.py"
        patched_02.write_text("""
import timm
class M:
    def __init__(self):
        self.backbone = timm.create_model('vit_large_patch16_384', pretrained=True, num_classes=0)
""", encoding="utf-8")
        c2_flaw, _, _ = run_cmd([str(ADV_DIR / "test_flaw_02_dead_imagenet_head.py"), "--target-file", str(flawed_02)])
        c2_patch, _, _ = run_cmd([str(ADV_DIR / "test_flaw_02_dead_imagenet_head.py"), "--target-file", str(patched_02)])
        print(f"  Flawed 02: exit {c2_flaw} (expected 1), Patched 02: exit {c2_patch} (expected 0)")
        if c2_flaw != 1 or c2_patch != 0:
            overall_pass = False

        # Flaw 03 isolated mock flaw vs patched
        print("\nTesting Flaw 03 isolated mock:")
        flawed_03 = tpath / "flawed_03.py"
        flawed_03.write_text("""
import torch.nn as nn
class BasicConv2d(nn.Module): pass
class RFBBlock(nn.Module): pass
class ReverseAttention(nn.Module): pass
class ChakraNetMicroRefiner(nn.Module): pass
""", encoding="utf-8")
        patched_03 = tpath / "patched_03.py"
        patched_03.write_text("""
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module): pass
""", encoding="utf-8")
        c3_flaw, _, _ = run_cmd([str(ADV_DIR / "test_flaw_03_dead_code.py"), "--target-file", str(flawed_03)])
        c3_patch, _, _ = run_cmd([str(ADV_DIR / "test_flaw_03_dead_code.py"), "--target-file", str(patched_03)])
        print(f"  Flawed 03: exit {c3_flaw} (expected 1), Patched 03: exit {c3_patch} (expected 0)")
        if c3_flaw != 1 or c3_patch != 0:
            overall_pass = False

        # Flaw 04 isolated mock flaw vs patched
        print("\nTesting Flaw 04 isolated mock:")
        flawed_04 = tpath / "flawed_04.py"
        flawed_04.write_text("""
class M:
    def forward(self, x):
        try:
            return x
        except RuntimeError:
            self.to('cpu')
""", encoding="utf-8")
        patched_04 = tpath / "patched_04.py"
        patched_04.write_text("""
class M:
    def forward(self, x):
        return x
""", encoding="utf-8")
        c4_flaw, _, _ = run_cmd([str(ADV_DIR / "test_flaw_04_oom_fallback.py"), "--target-file", str(flawed_04)])
        c4_patch, _, _ = run_cmd([str(ADV_DIR / "test_flaw_04_oom_fallback.py"), "--target-file", str(patched_04)])
        print(f"  Flawed 04: exit {c4_flaw} (expected 1), Patched 04: exit {c4_patch} (expected 0)")
        if c4_flaw != 1 or c4_patch != 0:
            overall_pass = False

        # Flaw 05 isolated mock flaw vs patched
        print("\nTesting Flaw 05 isolated mock:")
        flawed_05 = tpath / "flawed_05.py"
        flawed_05.write_text("""
class ChakraNet:
    def __init__(self):
        pass
    def segment_roi(self):
        tta = getattr(self, 'use_tta', True)
        return tta
""", encoding="utf-8")
        patched_05 = tpath / "patched_05.py"
        patched_05.write_text("""
class ChakraNet:
    def __init__(self, use_tta: bool = False):
        self.use_tta = use_tta
    def segment_roi(self):
        tta = getattr(self, 'use_tta', False)
        return tta
""", encoding="utf-8")
        c5_flaw, _, _ = run_cmd([str(ADV_DIR / "test_flaw_05_tta_enabled_by_default.py"), "--target-file", str(flawed_05)])
        c5_patch, _, _ = run_cmd([str(ADV_DIR / "test_flaw_05_tta_enabled_by_default.py"), "--target-file", str(patched_05)])
        print(f"  Flawed 05: exit {c5_flaw} (expected 1), Patched 05: exit {c5_patch} (expected 0)")
        if c5_flaw != 1 or c5_patch != 0:
            overall_pass = False

        # Flaw 06 isolated mock flaw vs patched
        print("\nTesting Flaw 06 isolated mock:")
        flawed_06 = tpath / "flawed_06.py"
        flawed_06.write_text("""
import torch
sd = torch.load('model.pth', map_location='cpu')
""", encoding="utf-8")
        patched_06 = tpath / "patched_06.py"
        patched_06.write_text("""
import torch
sd = torch.load('model.pth', map_location='cpu', weights_only=True)
""", encoding="utf-8")
        c6_flaw, _, _ = run_cmd([str(ADV_DIR / "test_flaw_06_unguarded_torch_load.py"), "--target-file", str(flawed_06)])
        c6_patch, _, _ = run_cmd([str(ADV_DIR / "test_flaw_06_unguarded_torch_load.py"), "--target-file", str(patched_06)])
        print(f"  Flawed 06: exit {c6_flaw} (expected 1), Patched 06: exit {c6_patch} (expected 0)")
        if c6_flaw != 1 or c6_patch != 0:
            overall_pass = False

        # Flaw 07 isolated mock flaw vs patched
        print("\nTesting Flaw 07 isolated mock:")
        flawed_07 = tpath / "flawed_07.py"
        flawed_07.write_text("""
class M:
    def load(self, sd):
        m, u = self.net.load_state_dict(sd, strict=False)
        print("warn missing keys")
""", encoding="utf-8")
        patched_07 = tpath / "patched_07.py"
        patched_07.write_text("""
class M:
    def load(self, sd):
        m, u = self.net.load_state_dict(sd, strict=False)
        if m or u:
            raise RuntimeError("Key mismatch!")
""", encoding="utf-8")
        c7_flaw, _, _ = run_cmd([str(ADV_DIR / "test_flaw_07_strict_false_state_dict.py"), "--target-file", str(flawed_07)])
        c7_patch, _, _ = run_cmd([str(ADV_DIR / "test_flaw_07_strict_false_state_dict.py"), "--target-file", str(patched_07)])
        print(f"  Flawed 07: exit {c7_flaw} (expected 1), Patched 07: exit {c7_patch} (expected 0)")
        if c7_flaw != 1 or c7_patch != 0:
            overall_pass = False

    print(f"\nOVERALL RESULT: {'PASS' if overall_pass else 'FAIL'}")
    sys.exit(0 if overall_pass else 1)

if __name__ == "__main__":
    run_tests()
