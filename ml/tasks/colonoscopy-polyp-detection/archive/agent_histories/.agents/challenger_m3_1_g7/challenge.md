# Adversarial Empirical Challenge Report: Archive Layouts, Path Mechanics & 4-Tier Asset Resolver

**Document ID:** CHALLENGE-M3-1-GEN7  
**Audited Report:** `COLAB_EVALUATION_AUDIT_REPORT.md` (AUDIT-COLAB-GPU-GEN7-M2)  
**Investigator:** Challenger M3-1 (Generation 7)  
**Role:** Empirical Challenger / Critic  
**Date:** 2026-09-08  
**Verification Harness:** Python 3.11.9 on Windows x64 (NTFS) + POSIX ext4 Simulation Engine  

---

## 1. Challenge Summary

**Overall Risk Assessment:** **HIGH**

Worker M2's forensic audit (`COLAB_EVALUATION_AUDIT_REPORT.md`) accurately diagnosed the primary root cause of the Colab execution failure—namely, the hardcoded `/content/drive/MyDrive/` root path assumption that bypassed synced subdirectories. However, an empirical stress-test of Worker M2's proposed **4-Tier Asset Resolver** and code artifacts revealed **critical internal contradictions, unhandled edge cases, and POSIX case-sensitivity blind spots** that will cause secondary execution failures in production cloud environments.

Specifically:
1. **Silent Fallback Bug (Lack of Fail-Fast):** Proposed `resolve_file` silently ignores invalid explicit CLI paths, falling back to ambient defaults and risking evaluation on incorrect checkpoints.
2. **Missing Tier 2 Environment Variable Support:** Despite claiming Tier 2 handles environment variables in the architecture diagram, the proposed `resolve_file` implementation has zero code checking `CHAKRA_WEIGHTS` or `CHAKRA_YOLO_WEIGHTS`.
3. **Re-introduction of Silent Dataset Skipping:** Worker M2 criticized legacy `verify_strict.py` for returning `None` on missing datasets, yet wrote the exact same silent return bug into Artifact 2 (`verify_dataset`), allowing `main()` to exit 0 with 0 evaluated images.
4. **POSIX Case-Sensitivity Blind Spot:** Worker M2 proposed `drive_root.glob('*chakra*')`. On Linux ext4 (Ubuntu / Google Colab), this is strictly case-sensitive and completely fails to match `ChakraModel` or `CHAKRAMODEL`.
5. **YOLO Checkpoint Hash Divergence:** Empirical inspection revealed that `best.pt` in `chakramodel-weights.zip` and `best.pt` in `chakramodel_weights_PRIVATE.zip` are two completely different models with 296 differing parameter tensors.

---

## 2. Empirical Verification of Archive Ecosystem

All three zip archives were verified empirically via `inspect_zips.py`. Below is the verified ground truth:

### 2.1 Archive Inventory & Cryptographic Hashes

| Archive Name | File Size (Bytes) | Size (MiB / MB) | Total Entries | Outer MD5 Hash | Verified Structure & Contents |
|---|---|---|---|---|---|
| `chakramodel_data_scripts.zip` | 240,662,934 | 229.51 MiB (240.66 MB) | 998 | `c861bd2822468cb5f70201bb41efafac` | **Top-level:** `data/`, `src/`. **Contains ZERO weights!** Data has 60 CVC-300 pairs, 380 CVC-ColonDB pairs. Scripts include `src/verify_strict.py`, `src/chakranet_segmenter.py`, `src/metrics_engine_v2.py`. |
| `chakramodel-weights.zip` | 1,155,023,765 | 1101.52 MiB (1.155 GB) | 3 | `4aa14d75aff01f3e4b44d41763de3afd` | **Completely FLAT!** Contains `best.pt` (6,209,450 B), `chakra_transformer_best.pth` (1,236,836,719 B), `conformal_calibration.json` (130 B). Zero `weights/` directory. |
| `chakramodel_weights_PRIVATE.zip` | 2,516,940,586 | 2400.34 MiB (2.517 GB) | 11 | `207f24fc646de6d24da38433a7f23908` | **Nested under `weights/`!** Contains 8 `.pth` / `.pt` files. `chakra_transformer_best.pth` matches public zip. However, `weights/best.pt` differs! |

### 2.2 Inner File Hashes and Parameter Verification

| File Inside Archive | Archive Source | Uncompressed Bytes | Inner MD5 Hash | Status / Match |
|---|---|---|---|---|
| `src/chakranet_segmenter.py` | `data_scripts.zip` | 19,561 | `2671a9bb12c1f3db2daf372dcb62074e` | Matches repo `src/chakranet_segmenter.py` |
| `src/metrics_engine_v2.py` | `data_scripts.zip` | 7,796 | `0c7487b45fd020b30fd5983715aa139f` | Matches repo root `metrics_engine_v2.py` |
| `src/verify_strict.py` | `data_scripts.zip` | 5,834 | `d2262627c352f8bbfb82eb17b1c142b7` | Legacy version with CPU mock commented out |
| `chakra_transformer_best.pth` | `weights.zip` | 1,236,836,719 | `49541d7ca35955c2a33ba1ded85e0a70` | Exact match with local disk and PRIVATE zip |
| `best.pt` | `weights.zip` | 6,209,450 | `7bc485770374c5b17d4721d774e71a1a` | Exact match with local `weights/best.pt` |
| `weights/best.pt` | `PRIVATE.zip` | 6,241,834 | `c4d248ce1b2a3d2394265d6f9e89f4be` | **DIVERGENT MODEL** (32,384 bytes larger; 296 differing tensors) |

---

## 3. Adversarial Challenges to Worker M2's Remediation

### Challenge 1: Silent Fallback Bug (Lack of Fail-Fast) in Proposed `resolve_file`
- **Severity:** **CRITICAL**
- **Assumption Challenged:** Worker M2 claimed the 4-Tier Resolver enforces strict fail-fast validation.
- **Attack Scenario:** A user specifies an explicit checkpoint path with a typographical error or obsolete path:
  ```bash
  python src/verify_strict.py --weights /content/drive/MyDrive/chakra_transformer_v2.pth
  ```
  In Artifact 2 (lines 669–675):
  ```python
  def resolve_file(filename: str, explicit_path: Optional[str], root: Path, subdirs=("weights", "")) -> Path:
      if explicit_path and Path(explicit_path).exists():
          return Path(explicit_path).resolve()
      for s in subdirs:
          candidate = root / s / filename if s else root / filename
          if candidate.exists():
              return candidate.resolve()
  ```
  Because `Path(explicit_path).exists()` is `False`, the function **silently discards the user's explicit parameter** and proceeds to search `root/weights/` and cloud fallback paths! If an old checkpoint exists at `root/weights/chakra_transformer_best.pth`, the script runs using the wrong checkpoint without emitting an error or warning.
- **Empirical Proof:** Verified via `test_asset_resolver.py` (`test_worker_m2_silent_fallback_bug_on_invalid_cli_arg`), where passing a non-existent path silently returned the fallback checkpoint.
- **Blast Radius:** Critical silent evaluation errors in automated benchmarking and experiment tracking.
- **Mitigation:**
  ```python
  if explicit_path is not None:
      p = Path(explicit_path.strip('\'"'))
      if not p.exists():
          raise FileNotFoundError(f"[Tier 1 Error] Explicitly provided path does not exist: '{explicit_path}'")
      return p.resolve()
  ```

---

### Challenge 2: Omission of Tier 2 Environment Variables in `resolve_file`
- **Severity:** **HIGH**
- **Assumption Challenged:** The 4-Tier Architecture specification states:
  *"Tier 2: Environment Variables (CHAKRAMODEL_ROOT, CHAKRA_WEIGHTS, etc.)"*
- **Attack Scenario:** A user deploys a containerized evaluation job on Vertex AI or Kubernetes, setting `CHAKRA_WEIGHTS=/mnt/models/chakra_best.pth`.
  Because Worker M2's `resolve_file` has no implementation for environment variables, it completely ignores `CHAKRA_WEIGHTS` and fails to locate the checkpoint.
- **Empirical Proof:** Verified in `test_asset_resolver.py` (`test_worker_m2_lacks_env_var_in_resolve_file`).
- **Blast Radius:** Cloud and CI/CD pipelines cannot inject model checkpoints via standard environment variables.
- **Mitigation:** Update `resolve_file` signature to accept `env_var: Optional[str] = None` and resolve via `os.environ.get(env_var)` before checking local candidate directories.

---

### Challenge 3: Re-introduction of Silent Dataset Skipping in Artifact 2
- **Severity:** **HIGH**
- **Assumption Challenged:** Worker M2 explicitly condemned silent returns on line 297:
  *"Silent Dataset Skipping: If an image directory path is incorrect, the function returns silently without raising an error. The user sees [DONE] with 0 evaluated images."*
- **Attack Scenario:** In Artifact 2 (lines 706–711), Worker M2 wrote:
  ```python
  if not images_dir.exists():
      print(f"[ERROR] Images directory not found: {images_dir}")
      return None
  if not masks_dir.exists():
      print(f"[ERROR] Masks directory not found: {masks_dir}")
      return None
  ```
  If `--data-root` is misconfigured or a folder name has an unexpected case or typo, `verify_dataset` prints `[ERROR]` and returns `None`. The execution loop in `main()` finishes without calculating metrics, and the Python process terminates with exit status `0`.
- **Empirical Proof:** Verified in `stress_test_edge_cases.py` (`test_silent_dataset_failure`).
- **Blast Radius:** Automated CI test suites report "SUCCESS" despite zero images being processed.
- **Mitigation:** `verify_dataset` MUST raise `FileNotFoundError` immediately, or `main()` MUST assert `len(results['Dice']) > 0`.

---

### Challenge 4: POSIX Case-Sensitivity Blind Spot in Artifact 1 Drive Discovery
- **Severity:** **HIGH**
- **Assumption Challenged:** Worker M2 claimed `candidate_dirs = list(drive_root.glob('*chakra*')) + [drive_root]` is *"100% immune to subfolder naming variations"*.
- **Attack Scenario:** A user syncs their Google Drive folder with Title Case: `MyDrive/ChakraModel` or `MyDrive/ChakraModel_Colab`.
  Google Colab runs on Ubuntu Linux (ext4 filesystem). On ext4, `glob('*chakra*')` is strictly case-sensitive. It matches only lowercase `chakra`.
- **Empirical Proof:** In `stress_test_edge_cases.py`, testing `fnmatchcase` under POSIX rules showed:
  - `chakramodel` -> MATCH
  - `ChakraModel` -> **BLIND SPOT (Fails on Linux/Colab)**
  - `CHAKRAMODEL` -> **BLIND SPOT (Fails on Linux/Colab)**
  - `ChakraModel_Colab` -> **BLIND SPOT (Fails on Linux/Colab)**
- **Blast Radius:** Cloud setup cell raises `FileNotFoundError` despite the project existing on Google Drive.
- **Mitigation:** Use case-insensitive list comprehension:
  ```python
  candidate_dirs = [p for p in drive_root.iterdir() if 'chakra' in p.name.lower() and p.is_dir()] + [drive_root]
  ```

---

### Challenge 5: Divergent `best.pt` YOLO Checkpoint Across Archives
- **Severity:** **MEDIUM**
- **Assumption Challenged:** All provided checkpoints of the same name represent identical model states.
- **Empirical Proof:**
  - `chakramodel-weights.zip`: `best.pt` size 6,209,450 bytes, MD5 `7bc485770374c5b17d4721d774e71a1a`. Matches local disk `weights/best.pt`.
  - `chakramodel_weights_PRIVATE.zip`: `weights/best.pt` size 6,241,834 bytes, MD5 `c4d248ce1b2a3d2394265d6f9e89f4be`.
  - PyTorch state_dict tensor comparison revealed **296 differing tensors**.
- **Blast Radius:** Unpacking `chakramodel_weights_PRIVATE.zip` silently substitutes a divergent YOLO detector, introducing uncontrollable variance into benchmark replication.
- **Mitigation:** Pin the expected MD5 of `best.pt` (`7bc485770374c5b17d4721d774e71a1a`) in the verification harness.

---

### Challenge 6: Broken Zip Archive Logic in Artifact 1 Staging Loop
- **Severity:** **MEDIUM**
- **Assumption Challenged:** Artifact 1 properly extracts either code or weight zip archives.
- **Attack Scenario:** In Artifact 1 (Cell 2):
  ```python
  for z_cand in [cdir / 'chakramodel_data_scripts.zip', cdir / 'chakramodel-weights.zip']:
      if z_cand.exists() and zip_src is None:
          zip_src = z_cand
  ...
  elif zip_src and zip_src.name == 'chakramodel_data_scripts.zip':
      with zipfile.ZipFile(zip_src, 'r') as zf:
          zf.extractall(local_project)
  ```
  If `chakramodel-weights.zip` is found first or is the only archive present, `zip_src` is assigned `chakramodel-weights.zip`. Line 557 checks `zip_src.name == 'chakramodel_data_scripts.zip'`, which evaluates to `False`. The code then aborts with `FileNotFoundError`, never extracting `chakramodel-weights.zip`!
- **Blast Radius:** Dead code in staging loop that prevents standalone weights archive decompression.
- **Mitigation:** Separate archive resolution into `data_code_zip` and `weights_zip`.

---

## 4. Empirical Stress Test Results

| Test Scenario | Implementation Tested | Expected Behavior | Actual Behavior | Verdict |
|---|---|---|---|---|
| **CLI Invalid Path** | Worker M2 `resolve_file` | Raise `FileNotFoundError` | Silently returned fallback checkpoint | **FAIL** (Vulnerability Proven) |
| **CLI Invalid Path** | Hardened Resolver | Raise `FileNotFoundError` | Raised `[Tier 1 Error] Explicitly provided checkpoint does not exist` | **PASS** |
| **Env Var Checkpoint** | Worker M2 `resolve_file` | Resolve from `CHAKRA_WEIGHTS` | Ignored env var; returned non-existent root path | **FAIL** (Missing Tier 2) |
| **Env Var Checkpoint** | Hardened Resolver | Resolve from `CHAKRA_WEIGHTS` | Resolved custom path cleanly | **PASS** |
| **Missing Dataset Dir** | Worker M2 `verify_dataset` | Halt execution / raise error | Printed `[ERROR]`, returned `None`, exited 0 | **FAIL** (Silent Skipping) |
| **Missing Dataset Dir** | Hardened Resolver | Raise `FileNotFoundError` | Raised `FileNotFoundError: Images directory does not exist` | **PASS** |
| **Drive Casing (`ChakraModel`)** | Worker M2 `drive_root.glob('*chakra*')` | Discover `ChakraModel` | 0 folders found under POSIX rules | **FAIL** (POSIX Blind Spot) |
| **Drive Casing (`ChakraModel`)** | Hardened case-insensitive search | Discover `ChakraModel` | Successfully discovered folder | **PASS** |
| **Repo Root Execution** | Hardened Resolver | Resolve root to `m:\chakramodel` | Resolved to `m:\chakramodel` | **PASS** |
| **Subfolder Execution** | Hardened Resolver | Traverse up to `m:\chakramodel` | Upwards traversal reached `m:\chakramodel` | **PASS** |
| **Flat Weights Archive** | Hardened Resolver | Find weights at root level | Resolved `chakra_transformer_best.pth` at root | **PASS** |
| **Spaces in Path** | Hardened Resolver | Clean quotes, handle spaces | Correctly resolved path with spaces | **PASS** |

---

## 5. Unchallenged Areas

1. **Ultralytics YOLO Inference Pipeline:** The bounding box crop expansion logic (`roi_padding = 0.25`) and thresholding logic (`threshold = 0.45`) match the verified ground-truth pipeline documented in `COLLABRUNTESTING.pdf`.
2. **PyTorch State Dict Prefix Stripping:** The dictionary comprehension `{k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in sd.items()}` correctly strips DDP and compilation prefixes without side effects.
3. **Single-Pass Weight Loading:** Bypassing double deserialization via `weights_path='skip'` in `ChakraNet` saves ~1.24 GB host RAM and is sound.

---

## 6. Actionable Recommendations for Final Implementation

1. **Enforce Tier 1 & 2 Fail-Fast:** Modify `find_project_root` and `resolve_file` so that if an explicit argument or environment variable is set, it MUST exist or raise immediately.
2. **Add Environment Variables to `resolve_file`:** Support `CHAKRA_WEIGHTS` and `CHAKRA_YOLO_WEIGHTS` in Tier 2.
3. **Replace Linux POSIX Globbing:** Replace `drive_root.glob('*chakra*')` with `[p for p in drive_root.iterdir() if 'chakra' in p.name.lower() and p.is_dir()]`.
4. **Make `verify_dataset` Fail-Fast:** Raise `FileNotFoundError` immediately if `images_dir` or `masks_dir` does not exist.
5. **Pin YOLO Checkpoint:** Enforce MD5 verification against `7bc485770374c5b17d4721d774e71a1a` to prevent accidental evaluation on the divergent checkpoint in `PRIVATE.zip`.
