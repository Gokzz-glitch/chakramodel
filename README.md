# ChakraModel

## Colonoscopy Polyp Detection System

**ChakraModel** is a Computer-Aided Detection (CADe) system for colonoscopy polyp detection, built for the Tata Centre 36-Hour Hackathon. 

The primary objective of this system is to bridge the "benchmark-to-clinic" gap by focusing on:
1. **Temporal Stability**: Eliminating frame-by-frame flicker using ByteTrack multi-object tracking.
2. **Artifact Robustness**: Handling clinical artifacts (water jets, reflections, blur) via targeted augmentation and hysteresis thresholding.

## Architecture
- **Base Detector**: YOLOv8m (via Ultralytics)
- **Temporal Consistency**: ByteTrack + EMA confidence smoothing
- **Artifact Handling**: Albumentations + custom thresholding

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
