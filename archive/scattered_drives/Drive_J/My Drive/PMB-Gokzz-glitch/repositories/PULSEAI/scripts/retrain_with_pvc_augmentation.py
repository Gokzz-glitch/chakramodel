#!/usr/bin/env python3
"""
Controlled Retraining with PVC-like Hard Negatives
===================================================
Purpose: Improve PVC discrimination for medical-grade gate compliance
Strategy: Add synthetic PVC-like patterns to Normal training samples
         to create harder negatives that force better model discrimination.

Target Metrics Post-Retraining:
  - Sensitivity: 55-65% (improve from 46.9%)
  - Specificity: 75-85% (improve from 70.8%)
  - 10-case accuracy: Maintain ≥90%
"""

import os
import sys
import json
import shutil
from datetime import datetime
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, optimizers, callbacks
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight
from sklearn.model_selection import train_test_split
from sklearn.utils import resample
from sklearn.preprocessing import OneHotEncoder
from keras.utils import to_categorical
import wfdb
from scipy import signal as sp_signal
import matplotlib.pyplot as plt

print("=" * 70)
print("CONTROLLED RETRAINING WITH PVC-LIKE HARD NEGATIVES")
print("=" * 70)

# Configuration
SEED = 42
FS = 360  # MIT-BIH sample rate
SEGMENT_LEN = 250  # samples per beat window
HALF_LEN = SEGMENT_LEN // 2
DATA_DIR = r'g:\My Drive\PULSEAI\mit-bih-arrhythmia-database-1.0.0'
OUTPUT_MODEL_FINAL = r'g:\My Drive\PULSEAI\backend\hctg_net_model.h5'
OUTPUT_MODEL_TMP = r'g:\My Drive\PULSEAI\backend\hctg_net_model_retrained.h5'
MIN_VALID_MODEL_BYTES = 100 * 1024

# AAMI class mapping
AAMI_MAP = {
    'N':'N', 'L':'N', 'R':'N', 'e':'N', 'j':'N',
    'A':'S', 'a':'S', 'J':'S', 'S':'S',
    'V':'V', 'E':'V',
    'F':'F',
    '/':'Q', 'f':'Q', 'Q':'Q'
}
CLASSES = ['N', 'S', 'V', 'F', 'Q']

def bandpass_filter(data, lowcut=0.5, highcut=40.0, fs=FS, order=4):
    nyq = 0.5 * fs
    b, a = sp_signal.butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return sp_signal.filtfilt(b, a, data)

def notch_filter(data, freq=60.0, fs=FS, Q=30):
    b, a = sp_signal.iirnotch(freq / (fs / 2.0), Q)
    return sp_signal.filtfilt(b, a, data)

def preprocess_signal(raw_signal, fs=FS):
    """Full preprocessing: baseline removal → notch → bandpass → normalize."""
    b, a = sp_signal.butter(4, 0.5 / (fs/2), btype='high')
    sig = sp_signal.filtfilt(b, a, raw_signal)
    sig = notch_filter(sig, freq=60.0, fs=fs)
    sig = bandpass_filter(sig, 0.5, 40.0, fs)
    return sig

def extract_segments(record_name, data_dir=DATA_DIR):
    """Extract beat-centered windows from MIT-BIH record."""
    try:
        record = wfdb.rdrecord(os.path.join(data_dir, record_name), channels=[0])
        annotation = wfdb.rdann(os.path.join(data_dir, record_name), 'atr')
    except Exception as e:
        print(f'  Error reading {record_name}: {e}')
        return [], []

    raw = record.p_signal[:, 0]
    sig = preprocess_signal(raw, fs=FS)

    segments, labels = [], []
    for r_peak, symbol in zip(annotation.sample, annotation.symbol):
        aami = AAMI_MAP.get(symbol)
        if aami is None:
            continue
        start = r_peak - HALF_LEN
        end = r_peak + HALF_LEN
        if start < 0 or end > len(sig):
            continue
        window = sig[start:end]
        std = window.std()
        if std < 1e-6:
            continue
        window = (window - window.mean()) / std
        segments.append(window.astype(np.float32))
        labels.append(aami)

    return segments, labels

def augment_normal_with_pvc_morphology(segment, strength=0.7):
    """
    Create synthetic PVC-like morphology in normal ECG:
    1. Amplify QRS region
    2. Invert T-wave
    3. Temporal shift
    4. Add high-frequency noise in QRS
    """
    aug = segment.copy()
    peak_idx = np.argmax(np.abs(aug))
    
    # QRS zone: ±40 samples around peak
    qrs_start = max(0, peak_idx - 40)
    qrs_end = min(len(aug), peak_idx + 40)
    
    # Amplify QRS
    aug[qrs_start:qrs_end] *= (1.3 + 0.2 * strength)
    
    # Invert T-wave
    t_start = min(len(aug), peak_idx + 60)
    t_end = min(len(aug), peak_idx + 140)
    if t_start < t_end:
        aug[t_start:t_end] *= -0.8
    
    # Add high-freq noise
    noise = np.random.normal(0, 0.15 * strength, qrs_end - qrs_start)
    aug[qrs_start:qrs_end] += noise
    
    # Temporal shift
    shift = np.random.randint(-5, 6)
    if shift != 0:
        aug = np.roll(aug, shift)
    
    # Normalize
    aug_std = np.std(aug)
    if aug_std > 1e-6:
        aug = (aug - np.mean(aug)) / aug_std
    
    return aug.astype(np.float32)

# ============================================================
# STEP 1: Extract all segments from MIT-BIH
# ============================================================
print("\n[STEP 1] Extracting segments from MIT-BIH database...")
all_segments, all_labels = [], []
available_records = [f.replace('.hea', '') for f in os.listdir(DATA_DIR) 
                     if f.endswith('.hea')]
print(f'Processing {len(available_records)} records...')

for rec in sorted(available_records):
    segs, lbls = extract_segments(rec)
    all_segments.extend(segs)
    all_labels.extend(lbls)
    print(f'  {rec}: {len(segs):4d} beats')

X = np.array(all_segments, dtype=np.float32)
y_raw = np.array(all_labels)

print(f'\nTotal segments extracted: {len(X)}')
unique, counts = np.unique(y_raw, return_counts=True)
for u, c in zip(unique, counts):
    print(f'  {u}: {c:5d} ({c/len(y_raw)*100:5.1f}%)')

# ============================================================
# STEP 2: Create PVC-like hard negatives (NEW)
# ============================================================
print("\n[STEP 2] Generating PVC-like hard negatives...")
np.random.seed(SEED)

normal_indices = np.where(y_raw == 'N')[0]
print(f'Original Normal samples: {len(normal_indices)}')

augmented_segments = []
augmented_labels = []

num_augmented = min(700, max(500, len(normal_indices) // 2))
for i in range(num_augmented):
    idx = normal_indices[np.random.randint(0, len(normal_indices))]
    aug_seg = augment_normal_with_pvc_morphology(X[idx], strength=np.random.uniform(0.5, 1.0))
    augmented_segments.append(aug_seg)
    augmented_labels.append('N')  # Still labeled as Normal (hard negative)

X_augmented = np.vstack([X, np.array(augmented_segments, dtype=np.float32)])
y_raw_augmented = np.concatenate([y_raw, np.array(augmented_labels)])

X = X_augmented
y_raw = y_raw_augmented

print(f'+ Augmented hard negatives: {num_augmented}')
print(f'Total after augmentation: {len(X)}')
unique_aug, counts_aug = np.unique(y_raw, return_counts=True)
for u, c in zip(unique_aug, counts_aug):
    print(f'  {u}: {c:5d}')

# ============================================================
# STEP 3: Encode and balance
# ============================================================
print("\n[STEP 3] Label encoding and class balancing...")
le = LabelEncoder()
le.fit(CLASSES)
y = le.transform(y_raw)

# Oversampling to balance classes
from imblearn.over_sampling import RandomOverSampler
ros = RandomOverSampler(random_state=SEED)
X_flat = X.reshape(len(X), -1)
X_res_flat, y_res = ros.fit_resample(X_flat, y)
X_res = X_res_flat.reshape(-1, SEGMENT_LEN, 1)
y_res_cat = to_categorical(y_res, num_classes=len(CLASSES))

print(f'After oversampling: {X_res.shape}')

# ============================================================
# STEP 4: Train/Val/Test split
# ============================================================
print("\n[STEP 4] Train/Val/Test split (70/15/15)...")
X_train, X_temp, y_train, y_temp = train_test_split(
    X_res, y_res_cat, test_size=0.30, random_state=SEED, stratify=y_res
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50, random_state=SEED
)

print(f'Train: {X_train.shape} | Val: {X_val.shape} | Test: {X_test.shape}')

# ============================================================
# STEP 5: Build HCTG-Net model
# ============================================================
print("\n[STEP 5] Building HCTG-Net (CNN + Transformer)...")

NUM_CLASSES = len(CLASSES)

def transformer_encoder_block(x, num_heads=4, key_dim=32, ff_dim=256, dropout=0.1):
    attn_out = layers.MultiHeadAttention(
        num_heads=num_heads, key_dim=key_dim, dropout=dropout
    )(x, x)
    attn_out = layers.Dropout(dropout)(attn_out)
    x = layers.Add()([x, attn_out])
    x = layers.LayerNormalization(epsilon=1e-6)(x)
    
    ff = layers.Dense(ff_dim, activation='gelu')(x)
    ff = layers.Dropout(dropout)(ff)
    ff = layers.Dense(x.shape[-1])(ff)
    x = layers.Add()([x, ff])
    x = layers.LayerNormalization(epsilon=1e-6)(x)
    return x

def build_hctg_net(input_length=SEGMENT_LEN, num_classes=NUM_CLASSES):
    inputs = tf.keras.Input(shape=(input_length, 1), name='ecg_input')
    
    # Stage 1: CNN Feature Extraction (Multi-Scale)
    a = layers.Conv1D(32, 3, padding='same', activation='relu')(inputs)
    a = layers.BatchNormalization()(a)
    b = layers.Conv1D(32, 7, padding='same', activation='relu')(inputs)
    b = layers.BatchNormalization()(b)
    c = layers.Conv1D(32, 15, padding='same', activation='relu')(inputs)
    c = layers.BatchNormalization()(c)
    
    x = layers.Concatenate()([a, b, c])
    x = layers.Conv1D(128, 3, padding='same', activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling1D(2)(x)
    
    x = layers.Conv1D(128, 3, padding='same', activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling1D(2)(x)
    
    x = layers.Conv1D(128, 3, padding='same', activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling1D(2)(x)
    
    # Stage 2: Transformer Encoder (×2)
    x = transformer_encoder_block(x, num_heads=4, key_dim=32, ff_dim=256, dropout=0.1)
    x = transformer_encoder_block(x, num_heads=4, key_dim=32, ff_dim=256, dropout=0.1)
    
    # Stage 3: Classification Head
    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.Dropout(0.4)(x)
    x = layers.Dense(128, activation='relu')(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(num_classes, activation='softmax', name='class_output')(x)
    
    model = tf.keras.Model(inputs, outputs, name='HCTG_Net')
    return model

model = build_hctg_net()
print(f'Total parameters: {model.count_params():,}')

# ============================================================
# STEP 6: Compile and train (controlled, 12 epochs)
# ============================================================
print("\n[STEP 6] Compiling and training model...")
print(f'Controlled retraining config:')
print(f'  - Epochs: 12 (with EarlyStopping, patience=4)')
print(f'  - Batch size: 256')
print(f'  - Learning rate: 1e-3 with adaptive reduction')
print(f'  - Loss: categorical_crossentropy')
print(f'  - Purpose: Improve PVC discrimination with augmented hard negatives')

y_train_int = np.argmax(y_train, axis=1)
cw = compute_class_weight('balanced', classes=np.arange(NUM_CLASSES), y=y_train_int)
class_weight_dict = dict(enumerate(cw))
print(f'  - Class weights: {dict((CLASSES[k], round(v, 3)) for k, v in class_weight_dict.items())}')

model.compile(
    optimizer=optimizers.Adam(learning_rate=1e-3),
    loss='categorical_crossentropy',
    metrics=['accuracy', tf.keras.metrics.AUC(name='auc', multi_label=False)]
)

cb_list = [
    callbacks.EarlyStopping(
        monitor='val_auc', patience=4, mode='max',
        restore_best_weights=True, verbose=1
    ),
    callbacks.ReduceLROnPlateau(
        monitor='val_loss', factor=0.5, patience=3,
        min_lr=1e-6, verbose=1
    ),
    callbacks.ModelCheckpoint(
        OUTPUT_MODEL_TMP, save_best_only=True,
        monitor='val_auc', mode='max', verbose=1
    )
]

print(f'\n🚀 Starting retraining...\n')
history = model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=12,
    batch_size=256,
    class_weight=class_weight_dict,
    callbacks=cb_list,
    verbose=1
)

# ============================================================
# STEP 7: Evaluate on test set
# ============================================================
print("\n[STEP 7] Evaluating on test set...")
test_results = model.evaluate(X_test, y_test, verbose=0)
test_acc, test_auc = test_results[1], test_results[2]
print(f'Test Accuracy: {test_acc:.4f}')
print(f'Test AUC: {test_auc:.4f}')

# ============================================================
# STEP 8: Save model
# ============================================================
print(f"\n[STEP 8] Saving retrained model...")
model.save(OUTPUT_MODEL_TMP)

tmp_size = os.path.getsize(OUTPUT_MODEL_TMP)
if tmp_size < MIN_VALID_MODEL_BYTES:
    raise RuntimeError(
        f"Temporary model appears invalid ({tmp_size} bytes). "
        "Aborting deployment to protect backend model."
    )

if os.path.exists(OUTPUT_MODEL_FINAL) and os.path.getsize(OUTPUT_MODEL_FINAL) > 0:
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{OUTPUT_MODEL_FINAL}.bak_{ts}"
    shutil.copy2(OUTPUT_MODEL_FINAL, backup_path)
    print(f'📦 Existing backend model backup: {backup_path}')

shutil.copy2(OUTPUT_MODEL_TMP, OUTPUT_MODEL_FINAL)
print(f'✅ Temp model saved: {OUTPUT_MODEL_TMP}')
print(f'✅ Backend model updated: {OUTPUT_MODEL_FINAL}')
print(f'   File size: {os.path.getsize(OUTPUT_MODEL_FINAL) / (1024*1024):.1f} MB')

# ============================================================
# Summary
# ============================================================
print("\n" + "="*70)
print("RETRAINING COMPLETE")
print("="*70)
print(f'Model (tmp):  {OUTPUT_MODEL_TMP}')
print(f'Model (live): {OUTPUT_MODEL_FINAL}')
print(f'Test Acc:     {test_acc:.4f}')
print(f'Test AUC:     {test_auc:.4f}')
print(f'Augmented:    {num_augmented} PVC-like hard negatives')
print(f'Epochs run:   {len(history.history["loss"])}')
print(f'Next step:    Full revalidation (benchmark + 10-case + audit)')
print("="*70)
