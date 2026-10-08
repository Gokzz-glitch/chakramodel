import json
from datetime import datetime

data = {
    "file_name": "yolov1 paper.pdf",
    "file_path": r"C:\Users\imgk3\Downloads\yolov1 paper.pdf",
    "timestamp_processed": "2026-09-04T14:58:22+05:30",
    "file_type": "pdf",
    "extracted_content": {
        "text": """You Only Look Once: Unified, Real-Time Object Detection
Joseph Redmon, Santosh Divvala, Ross Girshick, Ali Farhadi

Abstract
We present YOLO, a new approach to object detection. Prior work on object detection repurposes classifiers to perform detection. Instead, we frame object detection as a regression problem to spatially separated bounding boxes and associated class probabilities. A single neural network predicts bounding boxes and class probabilities directly from full images in one evaluation. Since the whole detection pipeline is a single network, it can be optimized end-to-end directly on detection performance.
Our unified architecture is extremely fast. Our base YOLO model processes images in real-time at 45 frames per second. A smaller version of the network, Fast YOLO, processes an astounding 155 frames per second while still achieving double the mAP of other real-time detectors. Compared to state-of-the-art detection systems, YOLO makes more localization errors but is less likely to predict false positives on background. Finally, YOLO learns very general representations of objects. It outperforms other detection methods, including DPM and R-CNN, when generalizing from natural images to other domains like artwork.

1. Introduction
...
YOLO is refreshingly simple: see Figure 1. A single convolutional network simultaneously predicts multiple bounding boxes and class probabilities for those boxes. YOLO trains on full images and directly optimizes detection performance. This unified model has several benefits over traditional methods of object detection.
First, YOLO is extremely fast. Since we frame detection as a regression problem we don’t need a complex pipeline. We simply run our neural network on a new image at test time to predict detections. Our base network runs at 45 frames per second with no batch processing on a Titan X GPU and a fast version runs at more than 150 fps. This means we can process streaming video in real-time with less than 25 milliseconds of latency. Furthermore, YOLO achieves more than twice the mean average precision of other real-time systems.

2. Unified Detection
Our system divides the input image into an S x S grid. If the center of an object falls into a grid cell, that grid cell is responsible for detecting that object.
Each grid cell predicts B bounding boxes and confidence scores for those boxes.
For evaluating YOLO on PASCAL VOC, we use S = 7, B = 2. PASCAL VOC has 20 labelled classes so C = 20. Our final prediction is a 7 x 7 x 30 tensor.

2.1. Network Design
Our network architecture is inspired by the GoogLeNet model for image classification. Our network has 24 convolutional layers followed by 2 fully connected layers.
Fast YOLO uses a neural network with fewer convolutional layers (9 instead of 24) and fewer filters in those layers.

2.2. Training
We train the network for about 135 epochs on the training and validation data sets from PASCAL VOC 2007 and 2012. Throughout training we use a batch size of 64, a momentum of 0.9 and a decay of 0.0005.
Dropout layer with rate = .5 after the first connected layer prevents co-adaptation between layers.

4. Experiments
Fast YOLO is the fastest object detection method on PASCAL; as far as we know, it is the fastest extant object detector. With 52.7% mAP, it is more than twice as accurate as prior work on real-time detection. YOLO pushes mAP to 63.4% while still maintaining real-time performance.
The best Fast R-CNN model achieves a mAP of 71.8% on the VOC 2007 test set. When combined with YOLO, its mAP increases by 3.2% to 75.0%.
On the VOC 2012 test set, YOLO scores 57.9% mAP.

5. Real-Time Detection In The Wild
YOLO is a fast, accurate object detector, making it ideal for computer vision applications.
"""
    },
    "key_metrics_and_values": [
        {"metric": "Base YOLO Speed", "value": "45 frames per second (fps)"},
        {"metric": "Fast YOLO Speed", "value": "155 frames per second (fps)"},
        {"metric": "Fast YOLO mAP (VOC 2007)", "value": "52.7%"},
        {"metric": "Base YOLO mAP (VOC 2007)", "value": "63.4%"},
        {"metric": "Base YOLO mAP (VOC 2012)", "value": "57.9%"},
        {"metric": "Combined YOLO + Fast R-CNN mAP", "value": "75.0%"},
        {"metric": "Input Image Resolution", "value": "448 x 448"},
        {"metric": "Grid Size (S)", "value": "7"},
        {"metric": "Bounding Boxes per Grid Cell (B)", "value": "2"},
        {"metric": "Labelled Classes (C)", "value": "20"},
        {"metric": "Final Prediction Tensor Size", "value": "7 x 7 x 30"},
        {"metric": "Convolutional Layers (Base YOLO)", "value": "24"},
        {"metric": "Convolutional Layers (Fast YOLO)", "value": "9"},
        {"metric": "Training Epochs", "value": "135"},
        {"metric": "Batch Size", "value": "64"},
        {"metric": "Momentum", "value": "0.9"},
        {"metric": "Weight Decay", "value": "0.0005"},
        {"metric": "Dropout Rate", "value": "0.5"}
    ]
}

# Write out the JSON
out_path = r"m:\chakramodel\yolov1 paper.pdf_extracted.json"
import os
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)
print(f"Data extracted and saved to {out_path}")
