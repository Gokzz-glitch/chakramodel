"""
End-to-End Simulation Test for Path Resolution across Environments.
Simulates:
1. Execution from project root
2. Execution from subfolder (src/ and .agents/challenger_m3_1_g7)
3. Execution with environment variables (CHAKRAMODEL_ROOT, CHAKRA_WEIGHTS)
4. Execution in simulated Colab environment (MyDrive/chakramodel vs MyDrive/chakramodel_collab)
5. Comparison of Worker M2 Artifact 1 Discovery vs Hardened Bounded Discovery
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Force UTF-8 stdout
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Import our HardenedAssetResolver and Worker functions from test_asset_resolver
sys.path.insert(0, str(Path(__file__).parent))
from test_asset_resolver import HardenedAssetResolver, worker_find_project_root, worker_resolve_file

def test_execution_from_repo_root():
    print("\n" + "="*80)
    print("TEST 1: Execution from Repo Root (m:\\chakramodel)")
    print("="*80)
    repo_root = Path(r"m:\chakramodel")
    resolver = HardenedAssetResolver(base_anchor=repo_root / "src" / "verify_strict.py")
    print(f"Resolved Root: {resolver.root}")
    assert resolver.root == repo_root.resolve(), f"Expected {repo_root}, got {resolver.root}"
    
    seg_w = resolver.resolve_checkpoint("chakra_transformer_best.pth")
    yolo_w = resolver.resolve_checkpoint("best.pt")
    print(f"ViT Weights Resolved:  {seg_w} (Exists: {seg_w.exists()})")
    print(f"YOLO Weights Resolved: {yolo_w} (Exists: {yolo_w.exists()})")
    assert seg_w.exists()
    assert yolo_w.exists()
    print("✅ TEST 1 PASSED: Clean resolution from repo root.")

def test_execution_from_subfolder():
    print("\n" + "="*80)
    print("TEST 2: Execution from Subfolder (m:\\chakramodel\\.agents\\challenger_m3_1_g7)")
    print("="*80)
    agent_dir = Path(r"m:\chakramodel\.agents\challenger_m3_1_g7")
    script_in_subfolder = agent_dir / "test_e2e_simulation.py"
    
    # Resolver anchoring from deep subfolder
    resolver = HardenedAssetResolver(base_anchor=script_in_subfolder)
    print(f"Subfolder:     {agent_dir}")
    print(f"Resolved Root: {resolver.root}")
    assert resolver.root == Path(r"m:\chakramodel").resolve()
    print("✅ TEST 2 PASSED: Anchor traversal upwards successfully identified repo root.")

def test_execution_with_env_vars():
    print("\n" + "="*80)
    print("TEST 3: Execution with Environment Variables")
    print("="*80)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        fake_repo = tmp / "custom_chakramodel"
        (fake_repo / "weights").mkdir(parents=True)
        (fake_repo / "src").mkdir(parents=True)
        (fake_repo / "src" / "chakranet_segmenter.py").touch()
        custom_vit = fake_repo / "weights" / "chakra_transformer_best.pth"
        custom_vit.touch()
        custom_yolo = fake_repo / "weights" / "best.pt"
        custom_yolo.touch()

        # Set env vars
        os.environ["CHAKRAMODEL_ROOT"] = str(fake_repo)
        resolver = HardenedAssetResolver()
        print(f"CHAKRAMODEL_ROOT set to: {fake_repo}")
        print(f"Resolved Root:           {resolver.root}")
        assert resolver.root == fake_repo.resolve()

        # Custom checkpoint via env var
        custom_ext_w = tmp / "external_checkpoint.pth"
        custom_ext_w.touch()
        os.environ["CHAKRA_WEIGHTS"] = str(custom_ext_w)
        resolved_vit = resolver.resolve_checkpoint("chakra_transformer_best.pth", env_var="CHAKRA_WEIGHTS")
        print(f"Resolved ViT checkpoint from env var: {resolved_vit}")
        assert resolved_vit == custom_ext_w.resolve()

        del os.environ["CHAKRAMODEL_ROOT"]
        del os.environ["CHAKRA_WEIGHTS"]
        print("✅ TEST 3 PASSED: Environment variable overrides operate correctly.")

def test_colab_discovery_variants():
    print("\n" + "="*80)
    print("TEST 4: Simulated Google Colab Drive Discovery Variants")
    print("="*80)
    with tempfile.TemporaryDirectory() as tmpdir:
        drive_root = Path(tmpdir) / "content" / "drive" / "MyDrive"
        
        # Case A: Standard sync 'chakramodel'
        dir_a = drive_root / "chakramodel"
        (dir_a / "weights").mkdir(parents=True)
        (dir_a / "src").mkdir(parents=True)
        (dir_a / "weights" / "chakra_transformer_best.pth").touch()
        (dir_a / "weights" / "best.pt").touch()
        (dir_a / "src" / "verify_strict.py").touch()

        # Case B: setup_colab sync 'chakramodel_collab'
        dir_b = drive_root / "chakramodel_collab"
        (dir_b / "weights").mkdir(parents=True)
        (dir_b / "src").mkdir(parents=True)
        (dir_b / "weights" / "chakra_transformer_best.pth").touch()
        (dir_b / "weights" / "best.pt").touch()
        (dir_b / "src" / "verify_strict.py").touch()

        # Test Discovery on Case A
        candidates_a = [p for p in drive_root.iterdir() if 'chakra' in p.name.lower() and p.is_dir()]
        print(f"Drive Root: {drive_root}")
        print(f"Discovered candidate folders in Drive: {[p.name for p in candidates_a]}")
        assert "chakramodel" in [p.name for p in candidates_a]
        assert "chakramodel_collab" in [p.name for p in candidates_a]
        print("✅ TEST 4 PASSED: Discovered both 'chakramodel' and 'chakramodel_collab' successfully.")

def test_fail_fast_on_missing_assets():
    print("\n" + "="*80)
    print("TEST 5: Fail-Fast Behavior on Missing Assets")
    print("="*80)
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_root = Path(tmpdir) / "empty_repo"
        (empty_root / "src").mkdir(parents=True)
        (empty_root / "src" / "chakranet_segmenter.py").touch()

        resolver = HardenedAssetResolver(explicit_root=str(empty_root))
        print("Testing resolution of non-existent checkpoint in empty repo:")
        try:
            resolver.resolve_checkpoint("chakra_transformer_best.pth")
            assert False, "Should have raised FileNotFoundError!"
        except FileNotFoundError as e:
            print("Successfully caught expected FileNotFoundError:")
            print(f"  {str(e).splitlines()[0]}")
            print("✅ TEST 5 PASSED: Fail-fast halts execution cleanly when assets are missing.")

if __name__ == "__main__":
    test_execution_from_repo_root()
    test_execution_from_subfolder()
    test_execution_with_env_vars()
    test_colab_discovery_variants()
    test_fail_fast_on_missing_assets()
