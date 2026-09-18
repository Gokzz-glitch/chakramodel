# U-Net Architecture Study Protocol (Baseline → Novel Model)

This protocol implements a complete study workflow for deriving a new segmentation architecture from recent U-Net-family baselines.

## 1) Baseline Selection

Start with 2–3 recent baselines:
- UNet 3+
- TransUNet
- Swin-UNet

## 2) Paper-by-Paper Architecture Documentation

For each baseline, record:
- Encoder design
- Skip-connection strategy
- Decoder or feature-fusion design
- Loss function(s)
- Compute cost (parameter count, FLOPs, inference speed)

Use: `docs/templates/unet_paper_comparison_template.md`

## 3) Reproducibility on a Fixed Dataset

Reproduce all baselines on one fixed dataset split and identical training settings.

Track each run in:
- `docs/templates/unet_reproducibility_log.csv`

Required invariants:
- Same train/val/test split for all models
- Same image resolution and preprocessing
- Same optimizer family and scheduler policy
- Same augmentation policy
- Same stopping and checkpoint criteria

## 4) Failure Pattern Analysis

After baseline runs, explicitly audit:
- Small object misses
- Boundary leakage / jagged masks
- Class imbalance collapse
- Noise/artifact sensitivity

Use:
- `docs/templates/unet_failure_ablation_matrix.csv`

## 5) Controlled Ablations

Change one factor per row:
- Attention block design
- Skip-fusion mechanism
- Decoder depth
- Normalization strategy
- Loss composition

Keep all other settings fixed per experiment row.

## 6) Novelty Definition

Define novelty only from observed gaps in baseline behavior and ablation evidence.

Document:
- Which failure mode is targeted
- Which architectural change addresses it
- Why existing baselines were insufficient

## 7) Fair Validation

Validate the proposed model against the same baselines under identical protocol constraints.

Minimum comparison:
- Accuracy metrics (Dice, IoU, Precision, Recall)
- Efficiency metrics (params, FLOPs, FPS/latency)

## 8) Final Reporting

Report:
- Best baseline vs proposed model
- Metric deltas (accuracy + efficiency)
- Failure-mode improvements
- Trade-offs and limitations

Completion criterion: improvements must be both measurable and reproducible under the same experimental budget.
