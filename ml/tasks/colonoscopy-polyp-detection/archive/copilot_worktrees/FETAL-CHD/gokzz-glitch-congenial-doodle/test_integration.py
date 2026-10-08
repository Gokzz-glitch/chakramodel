#!/usr/bin/env python
"""Comprehensive test of all model components."""
import torch
from pathlib import Path
from models import ImageEncoder, TabularEncoder, MultimodalClassifier
from inference import CHDPredictor
from data import CARDIUMDataModule

print("="*70)
print("FETAL-CHD MODEL INTEGRATION TEST")
print("="*70)

# Test 1: Model instantiation
print("\n[TEST 1] Model Architecture")
print("-" * 70)
try:
    img_model = ImageEncoder(num_classes=1, embed_dim=384, depth=12, num_heads=6)
    tab_model = TabularEncoder(input_dim=1, embed_dim=128, num_heads=4, num_layers=2, num_classes=1)
    multi_model = MultimodalClassifier(num_classes=2, fusion_dim=128)
    print("[PASS] ImageEncoder initialized (ViT 384-dim, 12 layers, 6 heads)")
    print("[PASS] TabularEncoder initialized (Transformer 128-dim, 2 layers, 4 heads)")
    print("[PASS] MultimodalClassifier initialized (image + tabular fusion)")
except Exception as e:
    print(f"[FAIL] {e}")
    exit(1)

# Test 2: Model forward pass
print("\n[TEST 2] Forward Pass")
print("-" * 70)
try:
    batch_imgs = torch.randn(2, 3, 224, 224)
    batch_tab = torch.randn(2, 1)
    
    with torch.no_grad():
        img_out = img_model(batch_imgs)
        tab_out = tab_model(batch_tab)
    
    print(f"[PASS] Image model output: {img_out.shape}")
    print(f"[PASS] Tabular model output: {tab_out.shape}")
    print(f"[PASS] Predictions generated successfully")
except Exception as e:
    print(f"[FAIL] {e}")
    exit(1)

# Test 3: Inference pipeline
print("\n[TEST 3] Inference Pipeline")
print("-" * 70)
try:
    img_archive = r'J:\My Drive\downloads\image_encoder.tar(CHd).gz'
    tab_archive = r'J:\My Drive\downloads\tabular_encoder.tar(chd).gz'
    
    predictor = CHDPredictor(img_archive, tab_archive, fold=0, device='cpu')
    print("[PASS] CHDPredictor loaded with pre-trained checkpoints")
    
    dataset_path = r'I:\My Drive\heartbeat\CARDIUM_dataset\CHD'
    sample_images = list(Path(dataset_path).rglob('*.png'))
    
    if sample_images:
        result = predictor.predict_from_image(str(sample_images[0]))
        print(f"[PASS] Single image prediction: {result['prediction']} ({result['confidence']:.1%})")
        print(f"       CHD: {result['CHD']:.4f}, Non_CHD: {result['Non_CHD']:.4f}")
    
    predictor.cleanup()
    print("[PASS] Temporary files cleaned up")
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: Dataset loading
print("\n[TEST 4] Dataset Loading")
print("-" * 70)
try:
    data = CARDIUMDataModule(
        data_root=r'I:\My Drive\heartbeat',
        fold=1,
        batch_size=4,
        augment_train=True
    )
    
    counts = data.get_class_counts()
    print(f"[PASS] CARDIUM dataset loaded (fold 1)")
    if counts['train']['Non_CHD'] > 0 or counts['train']['CHD'] > 0:
        print(f"       Train - CHD: {counts['train']['CHD']}, Non_CHD: {counts['train']['Non_CHD']}")
        print(f"       Val   - CHD: {counts['val']['CHD']}, Non_CHD: {counts['val']['Non_CHD']}")
        
        train_loader = data.train_loader()
        for images, labels, paths in train_loader:
            print(f"[PASS] Training batch: images {images.shape}, labels {labels.shape}")
            break
        
        val_loader = data.val_loader()
        for images, labels, paths in val_loader:
            print(f"[PASS] Validation batch: images {images.shape}, labels {labels.shape}")
            break
    else:
        print(f"       (No images found in fold structure - using include_all mode)")
        # Try with include_all
        data2 = CARDIUMDataModule(r'I:\My Drive\heartbeat', fold=1, batch_size=4)
        data2.train_dataset.include_all = True
        data2.val_dataset.include_all = True
        data2.train_dataset._load_dataset()
        data2.val_dataset._load_dataset()
        counts2 = data2.get_class_counts()
        print(f"       Train - CHD: {counts2['train']['CHD']}, Non_CHD: {counts2['train']['Non_CHD']}")
        print(f"[PASS] Dataset accessible")
        
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 5: Evaluation metrics
print("\n[TEST 5] Evaluation Utilities")
print("-" * 70)
try:
    from evaluate import CHDEvaluator
    
    evaluator = CHDEvaluator(device='cpu')
    
    # Simulate some predictions
    logits = torch.randn(10, 1)
    labels = torch.tensor([0, 1, 1, 0, 1, 0, 0, 1, 1, 0])
    
    evaluator.add_batch(logits, labels)
    metrics = evaluator.compute_metrics()
    
    print(f"[PASS] Evaluation metrics computed:")
    print(f"       Accuracy: {metrics['accuracy']:.3f}")
    print(f"       Precision: {metrics['precision']:.3f}")
    print(f"       Recall: {metrics['recall']:.3f}")
    print(f"       F1: {metrics['f1']:.3f}")
    print(f"       ROC-AUC: {metrics['roc_auc']:.3f}")
except Exception as e:
    print(f"[FAIL] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Summary
print("\n" + "="*70)
print("ALL TESTS PASSED")
print("="*70)
print("\nYour pre-existing models are ready to use!")
print("\nNext steps:")
print("1. Review QUICK_START.md for usage examples")
print("2. Run evaluate.py on your test set")
print("3. Use train.py to fine-tune on your data")
print("4. Deploy with inference.py for production")

