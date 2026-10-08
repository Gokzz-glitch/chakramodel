# ChakraModel End-to-End Pipeline Profiling Report

- **Device**: NVIDIA GeForce RTX 3050 Laptop GPU (cuda)
- **Total Hardware VRAM**: 4.00 GB
- **Frames Profiled**: 15 frames (768x576)

## 1. Latency Breakdown by Component

| Component / Pipeline Stage | Mean Latency (ms) | Std Dev (ms) | Standalone Throughput (FPS) | % of Frame Time (Single Polyp TTA) |
| :--- | :---: | :---: | :---: | :---: |
| **Stage 1: YOLOv8 Detection** | 19.67 | 2.61 | 50.8 FPS | 9.9% |
| **Crop, Padding & BBox Transform** | 0.04 | 0.01 | -- | 0.0% |
| **Letterbox & CPU->GPU Transfer** | 1.81 | 0.27 | -- | 0.9% |
| **ViT-Large Single Pass (FP32)** | 167.26 | 52.28 | 6.0 FPS | -- |
| **ViT-Large Single Pass (AMP FP16)** | 87.27 | 76.37 | 11.5 FPS | -- |
| └─ *ViT-Large Backbone Only (AMP)* | 62.61 | 0.58 | -- | 31.6% |
| └─ *TransposeConv Decoder + Upsample* | 3.66 | 0.24 | -- | 1.8% |
| **ViT-Large 3-Pass TTA (Status Quo)** | 175.15 | 3.38 | 5.7 FPS | 88.5% |
| **GPU->CPU Transfer + Contours** | 1.15 | 0.18 | -- | 0.6% |

## 2. End-to-End Scenario Throughput

| Operational Scenario | Total Latency (ms) | Effective Throughput (FPS) | Clinical Feasibility (<50ms / >20 FPS) |
| :--- | :---: | :---: | :---: |
| **Normal Mucosa (0 Polyps, YOLOv8 Only)** | 19.67 ms | 50.8 FPS | PASS (Real-Time) |
| **Single Polyp (1-Pass AMP, Optimized)** | 109.94 ms | 9.1 FPS | Near Real-Time (~10 FPS) |
| **Single Polyp (3-Pass TTA, Status Quo)** | 197.82 ms | 5.1 FPS | FAIL (~4-5 FPS Bottleneck) |
| **Two Polyps (Sequential 3-Pass TTA)** | 375.97 ms | 2.7 FPS | SEVERE FAIL (<2.5 FPS) |

## 3. GPU Memory Profile

- **Peak VRAM Allocated**: 1868.8 MB (1.82 GB)
- **Peak VRAM Reserved**: 1972.0 MB (1.93 GB)
- **Headroom on 4GB Hardware**: 2124.0 MB (~51.9% free)
