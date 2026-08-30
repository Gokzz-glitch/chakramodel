# ChakraModel

## Colonoscopy Polyp Detection System

**ChakraModel** is a Computer-Aided Detection (CADe) system for colonoscopy polyp detection, built for the Tata Centre 36-Hour Hackathon. 

The primary objective of this system is to bridge the "benchmark-to-clinic" gap by focusing on:
1. **Temporal Stability**: Eliminating frame-by-frame flicker using ByteTrack multi-object tracking.
2. **Artifact Robustness**: Handling clinical artifacts (water jets, reflections, blur) via targeted augmentation and hysteresis thresholding.

## Dual-Track Architecture (CNN & Transformer)

To address the trade-off between absolute accuracy and clinical real-time viability, ChakraModel provides two parallel tracks:

### 1. Clinical / Real-Time Track (CNN)
- **Location:** `src/` directory
- **Base Detector:** YOLOv8n (via Ultralytics)
- **Micro-Refiner:** PraNet (ResNet-34 backbone)
- **Speed:** ~49 FPS (capable of live video stream processing on edge devices)
- **Temporal Consistency:** ByteTrack + EMA confidence smoothing
- **Artifact Handling:** Albumentations + custom thresholding

### 2. Research / High-Accuracy Track (Vision Transformer)
- **Location:** `chakra_transformer/` directory
- **Architecture:** Vision Transformer (ViT) based segmentation
- **Speed:** Non-real-time (optimized for post-procedure auditing)
- **Advantage:** Maximum Dice score and precision for the most challenging flat polyps (Paris 0-IIb).

## Setup

1. **Environment:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Data:**
   The dataset is located in the `data/` directory.

## Project Structure
- `src/`: Core Python scripts (training, inference, evaluation, tracking).
- `data/`: Dataset and data processing scripts.
- `notebooks/`: Jupyter notebooks for EDA and Colab training.
- `configs/`: Model and system configuration files.
- `outputs/`: Training artifacts and logs.
