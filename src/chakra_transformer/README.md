# ChakraTransformer (Research Track)

## Selected paper model: ChakraXAttnUNet

The proposed cloud-trained model is a lightweight Swin-Tiny encoder-decoder
with cross-attention skip fusion and a boundary prediction head. It is
implemented in `xattn_unet.py`; training is provided by
`train_xattn_unet.py`. This replaces the ViT-Large prototype as the proposed
model. The ViT-Large model remains useful as a comparison baseline.

Training requires CUDA (Kaggle T4/P100 or Colab GPU):

```bash
python src/chakra_transformer/train_xattn_unet.py \
  --images /kaggle/input/<dataset>/images \
  --masks /kaggle/input/<dataset>/masks \
  --output /kaggle/working/xattn_unet
```

For video-derived data, split by original video/patient before creating the
image folders. Never place adjacent frames from one video in both train and
validation sets.

Prepare a dataset with the repository utility before training. It matches
image/mask stems, rejects ambiguous matches, creates a deterministic
group-level split, and can materialize the folders expected by the trainer:

First audit every mounted Kaggle input:

```bash
python data/scripts/audit_kaggle_datasets.py \
  --root /kaggle/input \
  --dataset-depth 3 \
  --output /kaggle/working/dataset_audit \
  --hash-images
```

Kaggle commonly mounts inputs as `/kaggle/input/<owner>/<dataset>/...`, so
depth 3 audits each dataset separately rather than combining all datasets into
one `datasets` directory. Review `summary.json` and `summary.csv`. In
particular, verify that masks are
actually binary segmentation images, not YOLO text labels or bounding boxes,
and check duplicate stems before selecting a source dataset.

An upload-ready notebook containing this ordered workflow is available at
`notebooks/Kaggle_XAttnUNet_Pilot.ipynb`. Upload it to Kaggle, attach the
datasets, enable a GPU, and run the cells in order.

```bash
python data/scripts/prepare_segmentation_manifest.py \
  --images /kaggle/input/source/images \
  --masks /kaggle/input/source/masks \
  --output /kaggle/working/source_prepared \
  --materialize
```

Run training separately for a fixed split:

```bash
python src/chakra_transformer/train_xattn_unet.py \
  --images /kaggle/working/source_prepared/images/train \
  --masks /kaggle/working/source_prepared/masks/train \
  --val-images /kaggle/working/source_prepared/images/val \
  --val-masks /kaggle/working/source_prepared/masks/val \
  --output /kaggle/working/xattn_pilot
```

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
