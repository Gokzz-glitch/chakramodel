# FETAL-CHD: Early Screening for Congenital Heart Disease with Ultrasound

Pre-trained model integration for fetal ultrasound CHD classification using Vision Transformer image encoders and tabular feature encoders.

For a reproducible Kaggle comparison across a supplied list of published
checkpoints, see [`KAGGLE_BENCHMARK.md`](KAGGLE_BENCHMARK.md) and
`kaggle_benchmark.py`.

## Dataset

**CARDIUM Dataset**: Fetal ultrasound images organized as:
- `CARDIUM_dataset/CHD/` - Congenital heart disease cases
- `CARDIUM_dataset/Non_CHD/` - Normal cases
- `cardium_images/` - 3-fold cross-validation split (fold_1, fold_2, fold_3)
  - Each fold: `train/` and `test/` subdirectories with CHD/Non_CHD classes

**Expected location**: `I:\My Drive\heartbeat\`

## Pre-trained Models

Two model archives included:
- **`image_encoder.tar(CHd).gz`** - Vision Transformer (ViT) for ultrasound images
  - Architecture: ViT with 12 blocks, 768-dim embeddings, 12 attention heads
  - Outputs: 2-class logits (CHD / Non_CHD)
  - 3 checkpoints: fold0/fold1/fold2 best models

- **`tabular_encoder.tar(chd).gz`** - MLP for structured clinical features
  - 3-layer network: input→128→64→2 classes
  - 3 checkpoints: fold0/fold1/fold2 best models

**Expected location**: `J:\My Drive\downloads\`

## Project Structure

```
.
├── models.py           # PyTorch model definitions (ImageEncoder, TabularEncoder, Multimodal)
├── inference.py        # Model loading & inference pipeline (CHDPredictor)
├── data.py             # Dataset loaders (CARDIUMDataset, CARDIUMDataModule)
├── train.py            # Training script with validation
├── evaluate.py         # Evaluation metrics and visualization
└── README.md           # This file
```

## Quick Start

### 1. Load Pre-trained Model for Inference

```python
from inference import CHDPredictor

predictor = CHDPredictor(
    image_encoder_path=r'J:\My Drive\downloads\image_encoder.tar(CHd).gz',
    tabular_encoder_path=r'J:\My Drive\downloads\tabular_encoder.tar(chd).gz',
    fold=0,  # Use fold 0 checkpoint
    device='cpu'  # or 'cuda'
)

# Single image prediction
result = predictor.predict_from_image(r'path\to\image.png')
print(f"Prediction: {result['prediction']} ({result['confidence']:.2%})")

# Batch prediction
results = predictor.predict_from_batch(r'I:\My Drive\heartbeat\CARDIUM_dataset\CHD')
predictor.cleanup()
```

### 2. Load Dataset

```python
from data import CARDIUMDataModule

data = CARDIUMDataModule(
    data_root=r'I:\My Drive\heartbeat',
    fold=1,
    batch_size=32,
    augment_train=True
)

train_loader = data.train_loader()
val_loader = data.val_loader()

# Check class balance
counts = data.get_class_counts()
print(counts)
```

### 3. Fine-tune with Existing Model

```python
from train import train_epoch, validate
from data import CARDIUMDataModule
from models import ImageEncoder
import torch

model = ImageEncoder(num_classes=2)
# Load pretrained weights...

data = CARDIUMDataModule(r'I:\My Drive\heartbeat', fold=1)
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
criterion = torch.nn.CrossEntropyLoss()

for epoch in range(10):
    train_epoch(model, data.train_loader(), optimizer, criterion, device='cpu')
    val_loss = validate(model, data.val_loader(), criterion, device='cpu')
    print(f"Epoch {epoch}: Val Loss {val_loss:.4f}")
```

## Requirements

```
torch>=2.0.0
torchvision>=0.15.0
timm>=0.9.0
Pillow>=9.0
numpy>=1.20
matplotlib>=3.3
scikit-learn>=1.0
```

Install with:
```bash
pip install torch torchvision timm pillow numpy matplotlib scikit-learn
```

## Model Details

### Vision Transformer (Image Encoder)
- Input: 224×224 RGB ultrasound images
- Patch embedding: 16×16 patches → 768-dim tokens
- 12 transformer blocks with 12-head attention
- Classification head: 768 → 2 classes
- Output: logits for CHD / Non_CHD

### Tabular MLP (Tabular Encoder)
- Input: 10-dim clinical features
- Hidden layers: 128 → 64 neurons with ReLU + Dropout(0.3)
- Output: 2-class logits

### Multimodal Fusion
- Concatenate image + tabular embeddings
- Final classifier: 512 → 2 classes

## Evaluation Metrics

Generated in `evaluate.py`:
- Accuracy, Precision, Recall, F1-score
- ROC-AUC and PR-AUC
- Confusion matrix visualization
- Per-fold cross-validation results
- Per-class performance breakdown

## File Structure Details

### models.py
- `ImageEncoder`: ViT implementation wrapping timm
- `TabularEncoder`: Simple MLP
- `MultimodalClassifier`: Fuses both encoders

### inference.py
- `ModelLoader`: Archive extraction and checkpoint loading
- `CHDPredictor`: End-to-end inference pipeline
  - `predict_from_image()`: Single image → CHD/Non_CHD probability
  - `predict_from_batch()`: Directory → results list
  - `cleanup()`: Temporary file management

### data.py
- `CARDIUMDataset`: PyTorch Dataset with label handling
- `CARDIUMDataModule`: Convenient train/val splitting
  - Handles 3-fold cross-validation
  - Optional training augmentation
  - Returns image + label + path tuples

## Next Steps

1. **Validate models**: Run `python inference.py` to test predictions
2. **Evaluate performance**: Use `evaluate.py` to generate ROC curves and confusion matrices
3. **Fine-tune**: Use `train.py` to adapt models to your specific ultrasound protocol
4. **Deploy**: Export models to ONNX or TorchScript for production inference

## Citation

If using these models, please cite your source dataset and any published methods.

## License

TBD - Follow institutional guidelines for model usage and data handling.
