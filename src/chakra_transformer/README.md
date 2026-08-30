# ChakraTransformer (Research Track)

Welcome to the **Research Track** of ChakraModel.

While the `src/` directory contains the CNN-based YOLO + PraNet pipeline optimized for real-time 49+ FPS inference, this folder contains the architecture designed for maximum accuracy on benchmark leaderboards.

## Why a Vision Transformer?
Vision Transformers (ViTs) utilize self-attention mechanisms to capture global context across an image far better than standard Convolutional Neural Networks (CNNs). This allows the model to distinguish extremely subtle features, such as completely flat polyps (Paris Classification Type 0-IIb) that blend deeply into the mucosal background.

## Trade-offs
- **Pros:** Highest possible Dice score and precision. Excellent for post-procedure auditing where live latency is not an issue.
- **Cons:** Significantly slower inference (often <15 FPS on laptop hardware) and high VRAM consumption.

## Usage
1. Ensure you have installed the transformer dependencies:
   ```bash
   pip install timm
   ```
2. You can inspect the model architecture:
   ```bash
   python transformer_segmenter.py
   ```
3. To train the transformer:
   ```bash
   python train_transformer.py --epochs 50 --batch-size 4
   ```
