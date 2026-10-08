"""
Challenger 1 Empirical Verification Suite for ChakraModel Phases 2-4.
Tests:
1. Git log sequence and messages
2. Secret protection: keys.txt untracked, physically intact
3. Sensitive logs protection: data/leads, results/outreach_logs untracked
4. Git status inspection for untracked critical files
5. Archive manifest: 100% bidirectional match (126 files, 69 iterate_copies, 57 one_off)
6. Zero source/data loss verification across restructuring
7. Combo notebooks 1 through 6 existence and validity
8. YOLOv8x weights existence (~136MB) and torch model loadability
9. Verified results JSON presence and valid schema
10. Results and Data READMEs existence and honest content
11. Restructured subpackages importability and backward compatibility shim
"""
import os
import re
import json
import subprocess
import pytest
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run_git(args):
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return result


class TestChallenger1Verification:

    def test_git_log_sequence(self):
        res = run_git(["log", "--oneline", "-5"])
        assert res.returncode == 0, f"git log failed: {res.stderr}"
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        assert len(lines) == 5, f"Expected 5 commits, got {len(lines)}"

        expected_prefixes = [
            "docs: update README with honest metrics",
            "docs: add architecture reconstruction and data flow map",
            "refactor: restructure repo into clean directory tree",
            "feat: track critical untracked evaluation scripts and results",
            "security: remove keys.txt and personal data from git tracking"
        ]

        for i, (line, expected) in enumerate(zip(lines, expected_prefixes)):
            commit_msg = " ".join(line.split()[1:])
            assert commit_msg.startswith(expected), (
                f"Commit {i} mismatch. Expected to start with '{expected}', got '{commit_msg}'"
            )

    def test_keys_txt_untracked_and_intact(self):
        # Must be untracked
        res = run_git(["ls-files", "keys.txt"])
        assert res.returncode == 0
        assert res.stdout.strip() == "", f"keys.txt is tracked in git: {res.stdout}"

        # Must physically exist on disk
        keys_path = os.path.join(REPO_ROOT, "keys.txt")
        assert os.path.isfile(keys_path), "keys.txt is missing from disk!"
        size = os.path.getsize(keys_path)
        assert size > 1000, f"keys.txt seems truncated or empty: {size} bytes"

    def test_sensitive_logs_untracked(self):
        res_leads = run_git(["ls-files", "data/leads/"])
        assert res_leads.returncode == 0
        assert res_leads.stdout.strip() == "", f"data/leads/ is tracked: {res_leads.stdout}"

        res_logs = run_git(["ls-files", "results/outreach_logs/"])
        assert res_logs.returncode == 0
        assert res_logs.stdout.strip() == "", f"results/outreach_logs/ is tracked: {res_logs.stdout}"

    def test_git_status_clean_critical(self):
        res = run_git(["status", "--porcelain"])
        assert res.returncode == 0
        # Check no production src/ or weights/ or core repo code is untracked
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("??"):
                path = line.split(maxsplit=1)[1]
                assert not path.startswith("src/"), f"Critical untracked source file found: {path}"
                assert not path.startswith("weights/"), f"Critical untracked weight file found: {path}"

    def test_archive_manifest_bidirectional(self):
        manifest_path = os.path.join(REPO_ROOT, "archive", "MANIFEST.md")
        assert os.path.isfile(manifest_path), "archive/MANIFEST.md does not exist"

        with open(manifest_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip().startswith("|") and "archive/" in l]

        assert len(lines) == 126, f"Expected 126 manifest table entries, got {len(lines)}"

        manifest_paths = set()
        iterate_count = 0
        one_off_count = 0

        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            rel_path = parts[2].replace("`", "").strip()
            manifest_paths.add(rel_path)
            if "archive/iterate_copies/" in rel_path:
                iterate_count += 1
            elif "archive/one_off/" in rel_path:
                one_off_count += 1

        assert iterate_count == 69, f"Expected 69 iterate_copies, got {iterate_count}"
        assert one_off_count == 57, f"Expected 57 one_off scripts, got {one_off_count}"

        # Check every manifest file exists on disk
        for mp in manifest_paths:
            full = os.path.join(REPO_ROOT, mp.replace("/", os.sep))
            assert os.path.isfile(full), f"Manifest file missing from disk: {mp}"

        # Check every file in archive/ on disk is in the manifest (except MANIFEST.md and python bytecode)
        disk_files = set()
        archive_root = os.path.join(REPO_ROOT, "archive")
        for root, dirs, files in os.walk(archive_root):
            if "__pycache__" in root:
                continue
            for file in files:
                if file != "MANIFEST.md" and not file.endswith(".pyc"):
                    rel = os.path.relpath(os.path.join(root, file), REPO_ROOT).replace("\\", "/")
                    disk_files.add(rel)

        assert len(disk_files) == 126, f"Expected 126 files on disk in archive/, got {len(disk_files)}"
        assert disk_files == manifest_paths, f"Mismatch: {disk_files ^ manifest_paths}"

    def test_no_source_or_data_deleted(self):
        # Diff c97f2173~1 to c97f2173
        res = run_git(["diff", "--name-status", "c97f2173~1", "c97f2173"])
        assert res.returncode == 0
        deleted = []
        for line in res.stdout.splitlines():
            if line.startswith("D\t"):
                deleted.append(line.split("\t")[1])

        # Verify that all deleted items from root were relocated
        relocations = {
            "Colab_GPU_Fast_Verify.ipynb": "notebooks/colab/Colab_GPU_Fast_Verify.ipynb",
            "monitor.py": "archive/one_off/monitor.py",
            "setup_colab.py": "archive/one_off/setup_colab.py",
        }
        for d in deleted:
            assert d in relocations, f"Unaccounted deleted file: {d}"
            target = relocations[d]
            assert os.path.isfile(os.path.join(REPO_ROOT, target)), f"Target {target} does not exist"

    def test_notebooks_combos_1_through_6(self):
        combos_dir = os.path.join(REPO_ROOT, "notebooks", "combos")
        expected_combos = [
            "Combo1_ChakraNet_Focal.ipynb",
            "Combo2_Topo_ChakraNet.ipynb",
            "Combo3_AdaBN_ChakraNet.ipynb",
            "Combo4_DiffusionAug_ChakraNet.ipynb",
            "Combo5_Federated_ChakraNet.ipynb",
            "Combo6_ChakraTransformer.ipynb",
        ]
        for nb_name in expected_combos:
            nb_path = os.path.join(combos_dir, nb_name)
            assert os.path.isfile(nb_path), f"Missing combo notebook: {nb_name}"
            with open(nb_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert "cells" in data and len(data["cells"]) > 0, f"Notebook {nb_name} is empty"

    def test_weights_yolo_yolov8x_integrity(self):
        weight_path = os.path.join(REPO_ROOT, "weights", "yolo", "yolov8x.pt")
        assert os.path.isfile(weight_path), f"weights/yolo/yolov8x.pt is missing"
        size = os.path.getsize(weight_path)
        # Expected ~136.89 MB (between 130MB and 140MB)
        size_mb = size / (1024 * 1024)
        assert 130.0 <= size_mb <= 140.0, f"Unexpected yolov8x.pt size: {size_mb:.2f} MB"

        # Load with torch to verify integrity
        ckpt = torch.load(weight_path, map_location="cpu", weights_only=False)
        assert isinstance(ckpt, dict), "Checkpoint is not a dictionary"
        assert "model" in ckpt, "Checkpoint missing 'model' key"
        assert hasattr(ckpt["model"], "eval"), "Loaded model has no eval method"

    def test_verified_results_completeness(self):
        verified_dir = os.path.join(REPO_ROOT, "results", "verified")
        required_files = [
            "combo1_metrics.json",
            "corrected_eval_kvasir_seg.json",
            "final_8_datasets_eval.json",
            os.path.join("kaggle_v5", "cross_dataset_results_v5.json"),
        ]
        for rf in required_files:
            fp = os.path.join(verified_dir, rf)
            assert os.path.isfile(fp), f"Missing verified result file: {rf}"
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert data, f"Verified result file is empty: {rf}"

    def test_readmes_exist_and_truthful(self):
        res_readme = os.path.join(REPO_ROOT, "results", "README.md")
        data_readme = os.path.join(REPO_ROOT, "data", "README.md")

        assert os.path.isfile(res_readme), "results/README.md does not exist"
        assert os.path.isfile(data_readme), "data/README.md does not exist"

        with open(res_readme, "r", encoding="utf-8") as f:
            res_content = f.read()
            assert "verified/" in res_content
            assert "historical/" in res_content
            assert "cross_dataset_results_v5.json" in res_content
            assert "0.8131" in res_content

        with open(data_readme, "r", encoding="utf-8") as f:
            data_content = f.read()
            assert "Kvasir-SEG" in data_content
            assert "Canary & Synthetic" in data_content or "synthetic" in data_content.lower()
            assert "ETIS-Larib" in data_content

    def test_restructured_src_importability(self):
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)

        from src.models.chakranet_segmenter import ChakraNet
        from src.models.pranet_resnet101 import PraNetResNet101
        from src.training.topo_loss import TopologicalLoss
        from src.chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter

        assert callable(ChakraNet)
        assert callable(PraNetResNet101)
        assert callable(TopologicalLoss)
        assert callable(ChakraTransformerSegmenter)

    def test_adversarial_detect_broken_subpackage_imports(self):
        """
        Adversarial test: stress tests whether scripts moved into subpackages
        can be executed directly without ModuleNotFoundError.
        Documents specific broken imports caused by restructuring.
        """
        broken_scripts = {}

        scripts_to_check = [
            "src/evaluation/quick_eval_kvasir.py",
            "src/evaluation/verify_strict.py",
            "src/evaluation/spot_check_eval.py",
            "src/conformal/conformal_calibration.py",
        ]

        for s in scripts_to_check:
            p = os.path.join(REPO_ROOT, s.replace("/", os.sep))
            res = subprocess.run(
                ["python", p, "--help"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if res.returncode != 0 and "ModuleNotFoundError" in res.stderr:
                # Capture the missing module
                m = re.search(r"ModuleNotFoundError: (.*)", res.stderr)
                broken_scripts[s] = m.group(1) if m else "ModuleNotFoundError"

        # Empirically prove and document the broken imports
        assert "src/evaluation/quick_eval_kvasir.py" in broken_scripts
        assert "chakranet_segmenter" in broken_scripts["src/evaluation/quick_eval_kvasir.py"]
        assert "src/evaluation/verify_strict.py" in broken_scripts
        assert "src/evaluation/spot_check_eval.py" in broken_scripts
        assert "src/conformal/conformal_calibration.py" in broken_scripts
