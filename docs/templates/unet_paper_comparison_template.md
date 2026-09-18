# U-Net Baseline Paper Comparison Template

> Copy this block once per paper and fill every field.

## Paper Metadata
- Paper title:
- Venue / year:
- Task / dataset focus:
- Code availability:
- Checkpoint availability:

## Architecture Summary
- Encoder backbone:
- Tokenization / stage hierarchy:
- Skip-connection strategy:
- Decoder / fusion strategy:
- Output head design:

## Training Objective
- Primary loss:
- Auxiliary loss(es):
- Class-imbalance handling:

## Compute Profile
- Input size:
- Parameters (M):
- FLOPs (G):
- Inference speed (FPS or ms/image):
- Hardware used:

## Reported Performance (from paper)
- Main benchmark datasets:
- Primary metric(s):
- Reported best score(s):

## Reproduction Plan (for this repository)
- Dataset split protocol:
- Fixed training settings:
- Target metrics:
- Expected bottlenecks:

## Failure-Mode Hypotheses
- Small-object failure risk:
- Boundary quality risk:
- Noise/artifact sensitivity risk:
- Domain shift risk:

## Candidate Ideas for Ablation
- Attention variant to test:
- Skip-fusion variant to test:
- Decoder depth variant to test:
- Normalization variant to test:
- Loss variant to test:
