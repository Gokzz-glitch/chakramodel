# Quick Integration Guide

## What's Included

Your project now has complete integration with pre-existing CHD classification models:

### Core Files
- **`models.py`** - Model architectures (ImageEncoder ViT, TabularEncoder Transformer)
- **`inference.py`** - End-to-end inference pipeline (`CHDPredictor` class)
- **`data.py`** - Dataset loaders for CARDIUM dataset with cross-validation
- **`train.py`** - Fine-tuning script with validation and checkpointing
- **`evaluate.py`** - Evaluation metrics and visualization (ROC, PR-AUC, confusion matrix)
- **`requirements.txt`** - All dependencies

## Model Specifications

**Image Encoder** (from `image_encoder.tar(CHd).gz`)
- Vision Transformer: 384-dim embeddings, 6 attention heads, 12 transformer blocks
- Input: 224×224 RGB ultrasound images  
- Output: Binary classification logits (CHD / Non_CHD)
- 3 checkpoints available: fold0, fold1, fold2

**Tabular Encoder** (from `tabular_encoder.tar(chd).gz`)
- Transformer-based: 128-dim embeddings, 4 heads, 2 encoder layers
- Input: Single clinical feature or structured data
- Output: Binary classification logits
- 3 checkpoints available: fold0, fold1, fold2

## Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Inference
```python
from inference import CHDPredictor

# Initialize with your model archives
predictor = CHDPredictor(
    image_encoder_path=r'J:\My Drive\downloads\image_encoder.tar(CHd).gz',
    tabular_encoder_path=r'J:\My Drive\downloads\tabular_encoder.tar(chd).gz',
    fold=0,  # Use fold 0 checkpoint
    device='cpu'  # Change to 'cuda' if available
)

# Predict single image
result = predictor.predict_from_image(r'path\to\ultrasound.png')
print(f"Prediction: {result['prediction']} ({result['confidence']:.2%})")
# Output: {'CHD': 0.012, 'Non_CHD': 0.988, 'prediction': 'Non_CHD', 'confidence': 0.988}

# Cleanup temporary files
predictor.cleanup()
```

### 3. Evaluate Models
```python
from data import CARDIUMDataModule
from models import ImageEncoder
from evaluate import evaluate_model
import torch

# Load dataset
data = CARDIUMDataModule(
    data_root=r'I:\My Drive\heartbeat',
    fold=1,
    batch_size=32
)

# Create model (load checkpoints if needed)
model = ImageEncoder(num_classes=1, embed_dim=384, depth=12, num_heads=6)
# model.load_state_dict(torch.load('path_to_checkpoint.pth'))

device = 'cuda' if torch.cuda.is_available() else 'cpu'
evaluator = evaluate_model(model, data.val_loader(), device=device)
```

### 4. Fine-tune Model
```python
from train import train_model
from data import CARDIUMDataModule
from models import ImageEncoder

data = CARDIUMDataModule(r'I:\My Drive\heartbeat', fold=1)
model = ImageEncoder(num_classes=1, embed_dim=384, depth=12, num_heads=6)

train_model(
    model,
    data.train_loader(),
    data.val_loader(),
    num_epochs=10,
    learning_rate=1e-4,
    device='cpu'
)
```

## Dataset Structure

Your CARDIUM dataset at `I:\My Drive\heartbeat\`:
```
CARDIUM_dataset/
├── CHD/
│   ├── aedxf00001rrfgkl0/
│   │   ├── 0_aedxf00001rrfgkl0.png
│   │   ├── 1_aedxf00001rrfgkl0.png
│   │   └── ...
│   └── ...
└── Non_CHD/
    └── ...

cardium_images/
└── cardium_images/
    ├── fold_1/
    │   ├── train/
    │   │   ├── CHD/
    │   │   └── Non_CHD/
    │   └── test/
    │       ├── CHD/
    │       └── Non_CHD/
    ├── fold_2/
    └── fold_3/
```

## Key Classes & Functions

### `CHDPredictor`
- `predict_from_image(path)` - Single prediction
- `predict_from_batch(directory)` - Directory batch prediction  
- `cleanup()` - Remove temporary files

### `CARDIUMDataModule`
- `train_loader()` - Training batches
- `val_loader()` - Validation batches
- `get_class_counts()` - Class distribution

### `CHDEvaluator`
- `compute_metrics()` - Accuracy, precision, recall, F1, AUC
- `plot_confusion_matrix()` - Visualization
- `plot_roc_curve()` - ROC-AUC plot
- `plot_pr_curve()` - Precision-Recall plot

## Next Steps

1. ✅ **Models integrated and tested** - Ready for inference
2. **Evaluate baseline** - Run evaluate.py on your test set
3. **Fine-tune** - Use train.py to adapt to your protocol
4. **Deploy** - Export to ONNX or TorchScript for production
5. **Validation** - Clinical validation on blind test set

## Troubleshooting

**Models not loading?**
- Verify archive paths in quotes are correct
- Check Python 3.8+ and PyTorch 2.0+
- Run `pip install -r requirements.txt`

**Out of memory?**
- Reduce batch size in CARDIUMDataModule
- Use `device='cpu'` and reduce image size

**Poor predictions?**
- Check image preprocessing (normalization, size)
- Evaluate on your specific ultrasound protocol
- Fine-tune with your data using train.py

## Support

For questions about model architecture or training, see:
- `models.py` - Architecture definitions
- `inference.py` - Model loading logic  
- `README.md` - Detailed documentation
