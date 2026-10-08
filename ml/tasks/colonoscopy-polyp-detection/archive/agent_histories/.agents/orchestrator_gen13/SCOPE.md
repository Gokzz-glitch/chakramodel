# Scope: ChakraModel Full Architecture Deep-Dive & Code Annotation

## Architecture & System Overview
ChakraModel is an integrated medical computer vision framework combining:
1. Detection Head: YOLO detection backbone and anchors/heads for region proposal / bounding boxes.
2. Body (Backbones): ViT-Large (`vit_large_patch16_384` patch embedding, 24 transformer blocks, multi-head self-attention, layer norms) and PraNet ResNet-101 feature extractors.
3. Decoders & Neck:
   - ChakraTransformer: Progressive upsampling decoder (linear projection from D=1024 -> reshape 2D spatial grid -> transposed convolutions / conv blocks -> segmentation logits) with conformal calibration.
   - ChakraNet / PraNet: Multi-scale feature aggregation (Parallel Partial Decoder - PPD, Reverse Attention Modules - RA) outputting saliency maps and boundary cues.

## Scope & Deliverables
### R1. Architectural Markdown Report
- Path: `docs/ARCHITECTURE_DEEP_DIVE.md`
- Content:
  - Comprehensive report decoding full architecture inch-by-inch down to tensor level.
  - Mermaid diagrams mapping entire data flow: Input image -> YOLO detection head -> ViT-Large backbone ("body") -> progressive upsampling / PPD decoders -> prediction logits & conformal calibration.
  - Detail exact tensor shape transformations at every major step (e.g., `[B, 3, 384, 384] -> [B, 576, 1024] -> [B, 1024, 24, 24] -> ... -> [B, 1, 384, 384]`).

### R2. Parameter-Level Mapping
- Path: `docs/parameter_mapping.txt` or `docs/parameter_mapping.csv`
- Content:
  - PyTorch summary-style deep mapping.
  - Every layer enumerated with layer name, parameter count (weights + biases), and exact input/output tensor shapes using notation like `[B, C, H, W]`.
  - Aggregated totals for heads, body, decoders, and full model.

### R3. Inline Code Annotation
- Path: Core model source files in `src/`:
  - `src/chakra_transformer/transformer_segmenter.py`
  - `src/models/chakranet_segmenter.py`
- Content:
  - Extensive inch-by-inch inline comments explaining what each block and line does.
  - Explicit references to "head", "body", "neck", "decoder", and exact tensor transformations (`# Tensor shape: [B, C, H, W] -> [B, C', H', W']`).
  - True line-by-line / block-by-block technical annotations, avoiding superficial docstrings.

## Acceptance Criteria
- Programmatic Verification:
  - `docs/ARCHITECTURE_DEEP_DIVE.md` exists and contains at least one `mermaid` block.
  - `docs/parameter_mapping.txt` (or `.csv`) exists and contains tensor shape notation (`[B, C, H, W]`).
  - Git diff verifies `src/chakra_transformer/transformer_segmenter.py` and `src/models/chakranet_segmenter.py` have extensive new inline comments.
- Independent Review:
  - Independent reviewer and auditor confirm inch-by-inch tensor explanations.
  - Forensic auditor confirms CLEAN integrity (no dummy code, genuine comments and mappings).
