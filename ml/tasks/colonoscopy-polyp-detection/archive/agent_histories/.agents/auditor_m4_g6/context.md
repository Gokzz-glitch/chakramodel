# Context for Forensic Auditor (Gen 6)

## Assigned Work Item
Binary Forensic Integrity Audit across all 4 Acceptance Criteria.

## Mandatory Checks
1. Check `src/chakranet_segmenter.py`:
   - Verify line 224 DDP prefix stripping logic (`replace("module.", "").replace("_orig_mod.", "")`).
   - Check for any hardcoded outputs, shortcut paths, or facades.
2. Check `src/verify_weights_load.py`:
   - Verify genuine forward pass through `ChakraNetMicroRefiner`.
   - Verify no mocked weights or fake return values.
3. Check `results/corrected_eval_kvasir_seg.json`:
   - Anti-fabrication analysis:
     * Check if DSC values correlate with IoU via the exact mathematical identity $IoU = DSC / (2 - DSC)$.
     * Check pixel counts ($pred\_pixels$, $gt\_pixels$, $intersection\_pixels$).
     * Verify timestamp and image filenames against real `data/kvasir-seg` dataset images.
     * Verify no hardcoded uniform distributions or dummy numbers.
4. Check `FIXES.md`:
   - Confirm all 5 mandatory sections exist:
     1. Root cause
     2. Exact lines changed
     3. Before/after diff
     4. Evidence from weight inspection
     5. Results after fix
   - Confirm timestamp: 2026-09-08.
   - Confirm no TBDs or unverified placeholders.
5. Check `notebooks/Kaggle_Final_Proof_Eval.ipynb`:
   - Verify cell 2 exists after imports, strips `module.` prefix, prints PASS/FAIL check, has timestamp 2026-09-08.
   - Verify valid notebook JSON structure.

## Deliverable
Write your audit report to `.agents/auditor_m4_g6/handoff.md` with:
- Forensic checks and evidence
- Binary Verdict: **CLEAN** or **INTEGRITY VIOLATION**
