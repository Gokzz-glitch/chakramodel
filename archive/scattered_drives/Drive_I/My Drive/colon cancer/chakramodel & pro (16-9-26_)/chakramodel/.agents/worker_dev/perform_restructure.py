import os
import sys
import shutil
import subprocess

REPO_ROOT = r"M:\chakramodel"
os.chdir(REPO_ROOT)

def run_git(cmd_args):
    res = subprocess.run(["git"] + cmd_args, capture_output=True, text=True, cwd=REPO_ROOT)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def is_git_tracked(path):
    rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
    code, out, _ = run_git(["ls-files", rel])
    return code == 0 and len(out) > 0

def safe_move(src_rel, dst_rel):
    src_path = os.path.join(REPO_ROOT, src_rel)
    dst_path = os.path.join(REPO_ROOT, dst_rel)
    if not os.path.exists(src_path):
        print(f"Skipping {src_rel} (does not exist)")
        return False
    
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    
    if is_git_tracked(src_path):
        code, out, err = run_git(["mv", src_rel.replace("\\", "/"), dst_rel.replace("\\", "/")])
        if code == 0:
            print(f"git mv: {src_rel} -> {dst_rel}")
            return True
        else:
            print(f"git mv failed for {src_rel} ({err}), falling back to shutil")
    
    shutil.move(src_path, dst_path)
    print(f"shutil move: {src_rel} -> {dst_rel}")
    return True

print("=== Starting Restructuring ===")

# 1. docs/
docs_moves = [
    ("CHAKRAMODEL_ANALYSIS_REPORT.md", "docs/CHAKRAMODEL_ANALYSIS_REPORT.md"),
    ("CHAKRAMODEL_VERSION_HISTORY.md", "docs/CHAKRAMODEL_VERSION_HISTORY.md"),
    ("POLYPGEN_INTEGRITY_REPORT.md", "docs/POLYPGEN_INTEGRITY_REPORT.md"),
    ("COLAB_EVALUATION_AUDIT_REPORT.md", "docs/audit/COLAB_EVALUATION_AUDIT_REPORT.md"),
    ("KAGGLE_DATASET_DECODING_REPORT.md", "docs/audit/KAGGLE_DATASET_DECODING_REPORT.md"),
    ("polypgen_integrity_report.json", "docs/audit/polypgen_integrity_report.json"),
    ("ChakraModel_Final_Paper.md", "docs/paper/ChakraModel_Final_Paper.md"),
]
for src, dst in docs_moves:
    safe_move(src, dst)

# 2. notebooks/
notebooks_moves = [
    ("notebooks/Combo1_ChakraNet_Focal.ipynb", "notebooks/combos/Combo1_ChakraNet_Focal.ipynb"),
    ("notebooks/deprecated/Combo2_Topo_ChakraNet.ipynb", "notebooks/combos/Combo2_Topo_ChakraNet.ipynb"),
    ("notebooks/deprecated/Combo3_AdaBN_ChakraNet.ipynb", "notebooks/combos/Combo3_AdaBN_ChakraNet.ipynb"),
    ("notebooks/deprecated/Combo4_DiffusionAug_ChakraNet.ipynb", "notebooks/combos/Combo4_DiffusionAug_ChakraNet.ipynb"),
    ("notebooks/deprecated/Combo5_Federated_ChakraNet.ipynb", "notebooks/combos/Combo5_Federated_ChakraNet.ipynb"),
    ("notebooks/Combo6_ChakraTransformer.ipynb", "notebooks/combos/Combo6_ChakraTransformer.ipynb"),
    ("notebooks/Combo6_ChakraTransformer.py", "notebooks/combos/Combo6_ChakraTransformer.py"),
    ("notebooks/deprecated/Combo4_DiffusionAug_ChakraNet.py", "notebooks/combos/Combo4_DiffusionAug_ChakraNet.py"),
    ("notebooks/deprecated/combo4_diffusion_aug_kaggle.py", "notebooks/combos/combo4_diffusion_aug_kaggle.py"),
    ("notebooks/deprecated/Combo5_Federated_ChakraNet.ipynb", "notebooks/combos/Combo5_Federated_ChakraNet.ipynb"),
    ("notebooks/deprecated/combo5_federated_colab.py", "notebooks/combos/combo5_federated_colab.py"),
    
    # Kaggle
    ("notebooks/Kaggle_Final_Proof_Eval.ipynb", "notebooks/kaggle/Kaggle_Final_Proof_Eval.ipynb"),
    ("notebooks/Kaggle_CrossVal_v5_PATHS_FIXED.ipynb", "notebooks/kaggle/Kaggle_CrossVal_v5_PATHS_FIXED.ipynb"),
    ("notebooks/Kaggle_CrossVal_v4_FIXED.ipynb", "notebooks/kaggle/Kaggle_CrossVal_v4_FIXED.ipynb"),
    ("notebooks/Kaggle_FixedPipeline_v2.ipynb", "notebooks/kaggle/Kaggle_FixedPipeline_v2.ipynb"),
    ("notebooks/Kaggle_HyperKvasir_Eval.ipynb", "notebooks/kaggle/Kaggle_HyperKvasir_Eval.ipynb"),
    ("notebooks/Kaggle_Master_CrossDataset_Eval_v3.ipynb", "notebooks/kaggle/Kaggle_Master_CrossDataset_Eval_v3.ipynb"),
    ("notebooks/Kaggle_PolypDB_Stress_Test.ipynb", "notebooks/kaggle/Kaggle_PolypDB_Stress_Test.ipynb"),
    ("notebooks/Kaggle_CVC_Video_Eval.ipynb", "notebooks/kaggle/Kaggle_CVC_Video_Eval.ipynb"),
    ("notebooks/ChakraModel_Kaggle_Evaluation.ipynb", "notebooks/kaggle/ChakraModel_Kaggle_Evaluation.ipynb"),
    ("notebooks/Kaggle_ChakraTransformer_Evaluation.ipynb", "notebooks/kaggle/Kaggle_ChakraTransformer_Evaluation.ipynb"),
    ("notebooks/Kaggle_ChakraTransformer_Evaluation_Standalone.ipynb", "notebooks/kaggle/Kaggle_ChakraTransformer_Evaluation_Standalone.ipynb"),
    ("AutoDiscover_Evaluation.ipynb", "notebooks/kaggle/AutoDiscover_Evaluation.ipynb"),
    ("Bulletproof_Evaluation.ipynb", "notebooks/kaggle/Bulletproof_Evaluation.ipynb"),
    ("Final_Evaluation_MultiCell.ipynb", "notebooks/kaggle/Final_Evaluation_MultiCell.ipynb"),
    ("kaggle_hardened_pipeline.ipynb", "notebooks/kaggle/kaggle_hardened_pipeline.ipynb"),
    ("kaggle_hardened_pipeline_multi.ipynb", "notebooks/kaggle/kaggle_hardened_pipeline_multi.ipynb"),
    ("kaggle_hardened_pipeline_multi_final.ipynb", "notebooks/kaggle/kaggle_hardened_pipeline_multi_final.ipynb"),

    # Colab
    ("notebooks/Colab_ChakraTransformer_Evaluation.ipynb", "notebooks/colab/Colab_ChakraTransformer_Evaluation.ipynb"),
    ("notebooks/colab_train.ipynb", "notebooks/colab/colab_train.ipynb"),
    ("Colab_GPU_Fast_Verify.ipynb", "notebooks/colab/Colab_GPU_Fast_Verify.ipynb"),
]
for src, dst in notebooks_moves:
    safe_move(src, dst)

# 3. weights/
weights_moves = [
    ("weights/chakra_transformer_best.pth", "weights/checkpoints/chakra_transformer_best.pth"),
    ("weights/chakra_transformer_best.pth.bak", "weights/checkpoints/chakra_transformer_best.pth.bak"),
    ("weights/combo1_best.pth", "weights/checkpoints/combo1_best.pth"),
    ("weights/combo2_best.pth", "weights/checkpoints/combo2_best.pth"),
    ("weights/pranet_kvasir_best.pth", "weights/checkpoints/pranet_kvasir_best.pth"),
    ("weights/best.pt", "weights/yolo/best.pt"),
    ("weights/yolov8n.pt", "weights/yolo/yolov8n.pt"),
    ("weights/yolo26n.pt", "weights/yolo/yolo26n.pt"),
    ("weights/yolo_custom_best.pt", "weights/yolo/yolo_custom_best.pt"),
    ("weights/best_backup_20260907.pt", "weights/yolo/best_backup_20260907.pt"),
    ("src/yolov8x.pt", "weights/yolo/yolov8x.pt"),
    ("weights/conformal_calibration.json", "weights/calibration/conformal_calibration.json"),
]
for src, dst in weights_moves:
    safe_move(src, dst)

# 4. src/ restructuring
src_moves = [
    # models
    ("src/chakranet_segmenter.py", "src/models/chakranet_segmenter.py"),
    ("src/pranet_resnet101.py", "src/models/pranet_resnet101.py"),
    
    # evaluation
    ("src/evaluate_all.py", "src/evaluation/evaluate_all.py"),
    ("src/run_corrected_eval.py", "src/evaluation/run_corrected_eval.py"),
    ("src/quick_eval_kvasir.py", "src/evaluation/quick_eval_kvasir.py"),
    ("src/spot_check_eval.py", "src/evaluation/spot_check_eval.py"),
    ("src/verify_minimal.py", "src/evaluation/verify_minimal.py"),
    ("src/verify_strict.py", "src/evaluation/verify_strict.py"),
    ("src/verify_eval.py", "src/evaluation/verify_eval.py"),
    ("src/verify_weights_load.py", "src/evaluation/verify_weights_load.py"),
    ("src/eval_pipeline.py", "src/evaluation/eval_pipeline.py"),
    ("src/eval_test.py", "src/evaluation/eval_test.py"),
    ("src/benchmark_kvasir.py", "src/evaluation/benchmark_kvasir.py"),
    ("src/benchmark_cross_dataset.py", "src/evaluation/benchmark_cross_dataset.py"),
    ("src/diagnostic_cross_dataset.py", "src/evaluation/diagnostic_cross_dataset.py"),
    ("src/benchmark_fps.py", "src/evaluation/benchmark_fps.py"),
    ("src/robustness_study.py", "src/evaluation/robustness_study.py"),
    ("src/ablation_study.py", "src/evaluation/ablation_study.py"),
    ("src/run_topo_ablation.py", "src/evaluation/run_topo_ablation.py"),
    ("src/run_all_combos.py", "src/evaluation/run_all_combos.py"),

    # training
    ("src/train_pranet.py", "src/training/train_pranet.py"),
    ("src/topo_loss.py", "src/training/topo_loss.py"),
    ("src/chakra_transformer/train_transformer.py", "src/training/train_transformer.py"),

    # detection
    ("src/train_yolo.py", "src/detection/train_yolo.py"),

    # inference
    ("src/infer_stream.py", "src/inference/infer_stream.py"),
    ("src/hybrid_refine.py", "src/inference/hybrid_refine.py"),
    ("src/export_tensorrt.py", "src/inference/export_tensorrt.py"),
    ("src/kaggle_video_inference.py", "src/inference/kaggle_video_inference.py"),
    ("src/test_videos_batch.py", "src/inference/test_videos_batch.py"),
    ("src/clinical_report.py", "src/inference/clinical_report.py"),
    ("src/paris_classifier.py", "src/inference/paris_classifier.py"),
    ("src/run_infer_eval_profile.py", "src/inference/run_infer_eval_profile.py"),
    ("src/run_profile.py", "src/inference/run_profile.py"),

    # conformal
    ("src/conformal_calibration.py", "src/conformal/conformal_calibration.py"),

    # anti_fabrication
    ("src/generate_judge_proof.py", "src/anti_fabrication/generate_judge_proof.py"),
]
for src, dst in src_moves:
    safe_move(src, dst)

print("=== Base Moves Complete ===")
