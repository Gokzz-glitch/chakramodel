# In-Depth Architectural Dissection: PraNet and ChakraNet Segmenters

> **Document Classification**: Deep Neural Architecture Specification & Tensor-Level Forensic Analysis  
> **Investigation Scope**: Tensor flow, layer-by-layer parameter derivation, Receptive Field Blocks (RFB), Parallel Partial Decoder (PPD), Reverse Attention (RA), and Vision Transformer segmentation  
> **Target Source Files**: `src/models/chakranet_segmenter.py`, `src/models/pranet_resnet101.py`, `notebooks/combos/Combo1_ChakraNet_Focal.ipynb`, `weights/checkpoints/combo1_best.pth`, `weights/checkpoints/chakra_transformer_best.pth`  
> **Author**: Explorer 2 (Milestone 1, Gen 13)  
> **Date**: 2026-09-10  

---

## 1. Executive Architectural Overview & The Dual-Identity Reality

In the ChakraModel codebase, the name **ChakraNet** represents a critical architectural dichotomy between two completely distinct deep learning paradigms developed across project generations:

1. **The Convolutional Paradigm (PraNet Lineage / Combo 1 & 2)**:
   - **Lineage**: Parallel Reverse Attention Network (PraNet, Fan et al., MICCAI 2020), adapted for endoscopic mucosal boundary segmentation.
   - **Core Engine**: Fully convolutional architecture employing a deep residual backbone, 4-stage Receptive Field Blocks (RFB) with dilated multi-branch convolutions, a Parallel Partial Decoder (PPD) for coarse global saliency localization, and a top-down cascade of 4 Reverse Attention (RA) modules equipped with CBAM (Convolutional Block Attention Module) to systematically erase the polyp interior and force gradient focus onto the lesion demarcation line.
   - **Implementations on Disk**:
     - `notebooks/combos/Combo1_ChakraNet_Focal.ipynb` & `archive/iterate_copies/Combo4_DiffusionAug_ChakraNet.py`: Max-Spec PraNet with a **ResNet-101** backbone and $C = 64$ channels (**45,671,821** trainable parameters).
     - `src/models/pranet_resnet101.py`: Deployed checkpoint-compatible model. Despite being named `PraNetResNet101`, it instantiates `models.resnet50` with $C = 48$ channels (**25,545,117** trainable parameters; **25,604,983** total state_dict elements including BatchNorm buffers), achieving a 100% architectural match (752/754 keys identical) with `weights/checkpoints/combo1_best.pth`.
     - `src/models/chakranet_segmenter.py` (lines 29–103): Defines `BasicConv2d`, `RFBBlock`, and `ReverseAttention` (without CBAM, 41,713 params each) as legacy/dead code blocks.

2. **The Vision Transformer Paradigm (ChakraTransformer / Combo 6 / Edge-Native Hybrid)**:
   - **Lineage**: Vision Transformer (`vit_large_patch16_384`, Dosovitskiy et al. / timm) combined with a 2-stage progressive transposed convolutional decode head.
   - **Core Engine**: 309.17M parameter model defined in `src/models/chakranet_segmenter.py` under the class `ChakraNetMicroRefiner` (docstring: *"ChakraTransformerSegmenter masquerading as ChakraNet for compatibility"*).
   - **Execution**: Takes $384 \times 384 \times 3$ padded square crops, computes all-to-all patch self-attention across 24 transformer blocks at 1024 embedding dimension, removes the CLS token, reshapes $576$ tokens into a $24 \times 24 \times 1024$ spatial bottleneck, and upscales via two $4\times$ `ConvTranspose2d` stages directly to a $384 \times 384 \times 1$ logit mask. Contains **no RFB, no PPD, and no Reverse Attention**.

This report dissects both systems inch-by-inch down to the exact tensor shapes, operations, and analytical parameter formulas.

---

## 2. ResNet Backbone Feature Extractor: ResNet-101 vs. ResNet-50

The PraNet feature extractor extracts a hierarchical 4-stage feature pyramid from the raw RGB endoscopic frame.

### 2.1 ResNet-101 Stage-by-Stage Architecture

ResNet-101 comprises an initial downsampling stem followed by 33 residual Bottleneck blocks grouped into 4 stages:

```
Input Frame [B, 3, H, W]
  │
  ▼
[Stem (enc0)]: Conv2d(3->64, 7x7, s=2, p=3) -> BatchNorm2d(64) -> ReLU -> MaxPool2d(3x3, s=2, p=1)
  │            Spatial Reduction: H -> H/2 -> H/4; Channels: 3 -> 64
  ▼
[Layer 1 (enc1 / res2)]: 3 Bottleneck Blocks (stride 1)
  │            Output: [B, 256, H/4, W/4]
  ▼
[Layer 2 (enc2 / res3)]: 4 Bottleneck Blocks (stride 2 on block 0)
  │            Output: [B, 512, H/8, W/8]
  ▼
[Layer 3 (enc3 / res4)]: 23 Bottleneck Blocks (stride 2 on block 0)
  │            Output: [B, 1024, H/16, W/16]
  ▼
[Layer 4 (enc4 / res5)]: 3 Bottleneck Blocks (stride 2 on block 0)
               Output: [B, 2048, H/32, W/32]
```

#### Bottleneck Block Structure
Every Bottleneck block in stage $i$ with bottleneck channels $C_{mid}$ and output channels $C_{out} = 4 \times C_{mid}$ performs:
1. `conv1`: $1 \times 1$ Conv2d ($C_{in} \to C_{mid}$, bias=False) + BatchNorm2d($C_{mid}$) + ReLU
2. `conv2`: $3 \times 3$ Conv2d ($C_{mid} \to C_{mid}$, stride=$s$, padding=1, bias=False) + BatchNorm2d($C_{mid}$) + ReLU
3. `conv3`: $1 \times 1$ Conv2d ($C_{mid} \to C_{out}$, bias=False) + BatchNorm2d($C_{out}$)
4. `downsample` (present in block 0 of each stage or when $C_{in} \neq C_{out}$): $1 \times 1$ Conv2d ($C_{in} \to C_{out}$, stride=$s$, bias=False) + BatchNorm2d($C_{out}$)
5. `residual`: $x_{out} = \text{ReLU}(x_{conv} + x_{shortcut})$

#### ResNet-101 vs. ResNet-50 Parameter Census

| Stage / Layer | Bottleneck Blocks (R-50) | Bottleneck Blocks (R-101) | Output Channels | Output Shape ($H=352$) | Output Shape ($H=384$) | Parameters (R-50) | Parameters (R-101) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `stem` (`conv1` + `bn1`) | — | — | 64 | `[B, 64, 88, 88]` | `[B, 64, 96, 96]` | 9,536 | 9,536 |
| `layer1` (`enc1` / res2) | 3 | 3 | 256 | `[B, 256, 88, 88]` | `[B, 256, 96, 96]` | 215,808 | 215,808 |
| `layer2` (`enc2` / res3) | 4 | 4 | 512 | `[B, 512, 44, 44]` | `[B, 512, 48, 48]` | 1,219,584 | 1,219,584 |
| `layer3` (`enc3` / res4) | 6 | **23** | 1024 | `[B, 1024, 22, 22]` | `[B, 1024, 24, 24]` | 7,098,368 | **26,090,496** |
| `layer4` (`enc4` / res5) | 3 | 3 | 2048 | `[B, 2048, 11, 11]` | `[B, 2048, 12, 12]` | 14,964,736 | 14,964,736 |
| **Backbone Subtotal (no FC)** | **16 blocks** | **33 blocks** | — | — | — | **23,508,032** | **42,500,160** |

*Key Takeaway*: ResNet-101 adds exactly 17 bottleneck blocks in `layer3` ($17 \times (1024 \times 256 + 256 \times 256 \times 9 + 256 \times 1024 + \text{BNs}) = 18,992,128$ additional parameters), expanding deep semantic capacity from 23.51M to 42.50M parameters.

---

## 3. Receptive Field Blocks (RFB 1–4): Multi-Branch Dilated Feature Extraction

Receptive Field Blocks (RFB) serve as the **Neck** of the PraNet architecture. Situated at each residual output $e_1, e_2, e_3, e_4$, each RFB compresses high-dimensional backbone features into a uniform channel dimension $C$ ($C = 48$ in `pranet_resnet101.py`; $C = 64$ in Max-Spec) while expanding the effective receptive field through asymmetric and dilated (atrous) convolutions.

```
Input x [B, C_in, H', W']
  ├─── Branch 0 ───────────────────────── BasicConv2d(1x1) ────────────────────────────────────────────────────────┐
  │                                                                                                                │
  ├─── Branch 1 ─ BasicConv2d(1x1) ── BasicConv2d(1x3) ── BasicConv2d(3x1) ── BasicConv2d(3x3, d=3, p=3) ────────┤
  │                                                                                                                │
  ├─── Branch 2 ─ BasicConv2d(1x1) ── BasicConv2d(1x5) ── BasicConv2d(5x1) ── BasicConv2d(3x3, d=5, p=5) ────────┤
  │                                                                                                                │
  ├─── Branch 3 ─ BasicConv2d(1x1) ── BasicConv2d(1x7) ── BasicConv2d(7x1) ── BasicConv2d(3x3, d=7, p=7) ────────┤
  │                                                                                                                │
  │                                                                         Concat [x0, x1, x2, x3] [B, 4*C, H', W']
  │                                                                                        │
  │                                                                                        ▼
  │                                                                         BasicConv2d(3x3, p=1) [B, C, H', W']
  │                                                                                        │
  └─── Residual Shortcut ──────────────── BasicConv2d(1x1) [B, C, H', W'] ─────────────────┼───► (+) ──► ReLU
                                                                                                        │
                                                                                                        ▼
                                                                                                Output [B, C, H', W']
```

### 3.1 Multi-Branch Mathematical Specification

Let $ic$ be the input channel dimension and $oc$ be the output channel dimension:

1. **Branch 0 (Local $1 \times 1$ Projection)**:
   - Operation: `BasicConv2d(ic, oc, kernel_size=1, stride=1, padding=0)`
   - Kernel Size: $1 \times 1$; Dilation: $d = 1$; Effective Receptive Field (ERF): $1$.
   - Parameters: $\text{Conv}(oc \times ic \times 1) + \text{BN}(2 \times oc) = ic \cdot oc + 2 \cdot oc$.
   - Shape: $[B, ic, H', W'] \to [B, oc, H', W']$.

2. **Branch 1 (Medium Context, $d=3$)**:
   - Step 1: `BasicConv2d(ic, oc, 1)` $\to [B, oc, H', W']$.
   - Step 2: `BasicConv2d(oc, oc, kernel_size=(1, 3), padding=(0, 1))` $\to$ Asymmetric horizontal 1D convolution.
   - Step 3: `BasicConv2d(oc, oc, kernel_size=(3, 1), padding=(1, 0))` $\to$ Asymmetric vertical 1D convolution.
     *Design Rationale*: The $(1\times 3) + (3\times 1)$ sequence factorizes a standard $3\times 3$ convolution, reducing parameter cost from $9 \cdot oc^2$ to $6 \cdot oc^2$ (a 33.3% reduction) while ensuring spatial symmetry.
   - Step 4: `BasicConv2d(oc, oc, kernel_size=3, padding=3, dilation=3)` $\to$ Dilated conv with dilation rate $d = 3$.
     $$\text{ERF} = k + (k - 1)(d - 1) = 3 + 2 \times 2 = 7.$$
   - Branch 1 Parameters: $(ic \cdot oc + 2oc) + 2 \times (3 \cdot oc^2 + 2oc) + (9 \cdot oc^2 + 2oc) = ic \cdot oc + 15 \cdot oc^2 + 8 \cdot oc$.

3. **Branch 2 (Large Context, $d=5$)**:
   - Step 1: `BasicConv2d(ic, oc, 1)` $\to [B, oc, H', W']$.
   - Step 2: `BasicConv2d(oc, oc, kernel_size=(1, 5), padding=(0, 2))` $\to$ Asymmetric horizontal conv.
   - Step 3: `BasicConv2d(oc, oc, kernel_size=(5, 1), padding=(2, 0))` $\to$ Asymmetric vertical conv.
     *Factorization*: $5 + 5 = 10 \cdot oc^2$ vs. $25 \cdot oc^2$ for full $5\times 5$ (a 60% reduction).
   - Step 4: `BasicConv2d(oc, oc, kernel_size=3, padding=5, dilation=5)` $\to$ Dilated conv with dilation rate $d = 5$.
     $$\text{ERF} = 3 + 2 \times 4 = 11.$$
   - Branch 2 Parameters: $(ic \cdot oc + 2oc) + 2 \times (5 \cdot oc^2 + 2oc) + (9 \cdot oc^2 + 2oc) = ic \cdot oc + 19 \cdot oc^2 + 8 \cdot oc$.

4. **Branch 3 (Global Lesion Context, $d=7$)**:
   - Step 1: `BasicConv2d(ic, oc, 1)` $\to [B, oc, H', W']$.
   - Step 2: `BasicConv2d(oc, oc, kernel_size=(1, 7), padding=(0, 3))` $\to$ Asymmetric horizontal conv.
   - Step 3: `BasicConv2d(oc, oc, kernel_size=(7, 1), padding=(3, 0))` $\to$ Asymmetric vertical conv.
     *Factorization*: $7 + 7 = 14 \cdot oc^2$ vs. $49 \cdot oc^2$ for full $7\times 7$ (a 71.4% reduction).
   - Step 4: `BasicConv2d(oc, oc, kernel_size=3, padding=7, dilation=7)` $\to$ Dilated conv with dilation rate $d = 7$.
     $$\text{ERF} = 3 + 2 \times 6 = 15.$$
   - Branch 3 Parameters: $(ic \cdot oc + 2oc) + 2 \times (7 \cdot oc^2 + 2oc) + (9 \cdot oc^2 + 2oc) = ic \cdot oc + 23 \cdot oc^2 + 8 \cdot oc$.

5. **Concatenation & Fusion (`conv_cat`)**:
   - Concatenation along channel axis: $x_{cat} = [x_0, x_1, x_2, x_3] \in \mathbb{R}^{B \times 4oc \times H' \times W'}$.
   - Fusion Convolution: `BasicConv2d(4 * oc, oc, kernel_size=3, padding=1)`.
   - Parameters: $(4 \cdot oc) \times oc \times 9 + 2 \cdot oc = 36 \cdot oc^2 + 2 \cdot oc$.

6. **Residual Shortcut & Addition (`conv_res`)**:
   - Linear projection: `BasicConv2d(ic, oc, kernel_size=1)`.
   - Parameters: $ic \cdot oc + 2 \cdot oc$.
   - Final Activation: $x_{out} = \text{ReLU}(\text{conv\_cat}(x_{cat}) + \text{conv\_res}(x)) \in \mathbb{R}^{B \times oc \times H' \times W'}$.

### 3.2 Exact Closed-Form Parameter Equation for RFB

Summing all branches, fusion, and residual:
$$\text{Params}_{\text{RFB}}(ic, oc) = 5 \times ic \times oc + 93 \times oc^2 + 30 \times oc$$

#### RFB Parameter Verification Matrix

| Module | Input Channels ($ic$) | Output Channels ($oc$) | Branch 0 | Branch 1 | Branch 2 | Branch 3 | Fusion (`cat`) | Shortcut (`res`) | Total Parameters ($oc=48$) | Total Parameters ($oc=64$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RFB-1** | 256 (`layer1`) | 48 / 64 | 12,384 | 47,232 | 56,448 | 65,664 | 83,040 | 12,384 | **277,152** | **464,768** |
| **RFB-2** | 512 (`layer2`) | 48 / 64 | 24,672 | 59,520 | 68,736 | 77,952 | 83,040 | 24,672 | **338,592** | **546,688** |
| **RFB-3** | 1024 (`layer3`) | 48 / 64 | 49,248 | 84,096 | 93,312 | 102,528 | 83,040 | 49,248 | **461,472** | **710,528** |
| **RFB-4** | 2048 (`layer4`) | 48 / 64 | 98,400 | 133,248 | 142,464 | 151,680 | 83,040 | 98,400 | **707,232** | **1,038,208** |
| **Total RFB** | — | — | — | — | — | — | — | — | **1,784,448** | **2,760,192** |

*(Note: Analytical formulas verified by direct parameter count against PyTorch modules down to 0 error).*

---

## 4. Parallel Partial Decoder (PPD): High-Level Context Aggregation & Global Saliency

The Parallel Partial Decoder acts as the primary global localization engine. In conventional encoder-decoder architectures (e.g., U-Net), decoders aggregate all feature stages ($e_1, e_2, e_3, e_4$). However, low-level features ($e_1$) contain severe background endoscopic clutter (specular reflections, lumen folds, debris). The PPD strategically discards low-level features during coarse localization, aggregating only high-level semantic features to generate an initial global saliency map $S_g$.

```
 r4 [B, C, H/32, W/32] ────── Bilinear Upsample (x4) ──────► [B, C, H/8, W/8] ──┐
                                                                                  │
 r3 [B, C, H/16, W/16] ────── Bilinear Upsample (x2) ──────► [B, C, H/8, W/8] ──┼──► Concat [B, 3*C or 4*C, H/8, W/8]
                                                                                  │         │
 r2 [B, C, H/8,  W/8]  ────────────────────────────────────► [B, C, H/8, W/8] ──┤         ▼
                                                                                  │    ppd_conv (3x3, BN, ReLU)
[r1_down in 4-input variant: Bilinear Downsample (x0.5)] ──► [B, C, H/8, W/8] ──┘         │ [B, C, H/8, W/8]
                                                                                            ▼
                                                                                       ppd_out (1x1 Conv)
                                                                                            │
                                                                                            ▼
                                                                               Global Saliency S_g [B, 1, H/8, W/8]
```

### 4.1 Spatial Alignment & Concatenation
The anchor resolution of the PPD is set to the spatial dimensions of $r_2$ ($H/8 \times W/8$):
- For $352 \times 352$ input: Anchor grid is $44 \times 44$.
- For $384 \times 384$ input: Anchor grid is $48 \times 48$.

Spatial Interpolations:
$$r_{3\_up} = \text{Interpolate}(r_3, \text{size}=\text{shape}(r_2)[2:], \text{mode}=\text{'bilinear'}, \text{align\_corners}=\text{False})$$
$$r_{4\_up} = \text{Interpolate}(r_4, \text{size}=\text{shape}(r_2)[2:], \text{mode}=\text{'bilinear'}, \text{align\_corners}=\text{False})$$

### 4.2 Variant Analysis: 3-Input vs. 4-Input PPD

1. **Standard 3-Input PPD (Combo 1 Max-Spec / MICCAI 2020 PraNet)**:
   - Concatenation: $F_{ppd\_in} = [r_2, r_{3\_up}, r_{4\_up}] \in \mathbb{R}^{B \times 3C \times (H/8) \times (W/8)}$.
   - `ppd_conv`: `BasicConv2d(3 * C, C, kernel_size=3, padding=1)`
     $$\text{Params} = (3C) \times C \times 9 + 2C = 27 \cdot C^2 + 2C.$$
     For $C = 64$: $27 \times 4096 + 128 = 110,720$ parameters.
     For $C = 48$: $27 \times 2304 + 96 = 62,304$ parameters.

2. **4-Input PPD (`pranet_resnet101.py` / `combo1_best.pth`)**:
   - $r_1$ ($H/4 \times W/4$) is bilinearly downsampled to $H/8 \times W/8$:
     $$r_{1\_down} = \text{Interpolate}(r_1, \text{size}=\text{shape}(r_2)[2:], \text{mode}=\text{'bilinear'}, \text{align\_corners}=\text{False})$$
   - Concatenation: $F_{ppd\_in} = [r_{1\_down}, r_2, r_{3\_up}, r_{4\_up}] \in \mathbb{R}^{B \times 4C \times (H/8) \times (W/8)}$.
   - `ppd_conv`: `BasicConv2d(4 * C, C, kernel_size=3, padding=1)`
     $$\text{Params} = (4C) \times C \times 9 + 2C = 36 \cdot C^2 + 2C.$$
     For $C = 48$: $36 \times 2304 + 96 = \mathbf{83,040}$ parameters. (Exactly matches `enc0` through `ppd_conv` in `combo1_best.pth`).

3. **Global Saliency Projection (`ppd_out` / `ppd_pred`)**:
   - Operation: `nn.Conv2d(C, 1, kernel_size=1, bias=True)`.
   - Parameters: $C \times 1 \times 1 + 1 = C + 1$.
     For $C = 48$: $48 + 1 = \mathbf{49}$ parameters.
     For $C = 64$: $64 + 1 = \mathbf{65}$ parameters.
   - Output: Raw logit map $S_g \in \mathbb{R}^{B \times 1 \times (H/8) \times (W/8)}$.

---

## 5. Reverse Attention (RA 1–4) Modules: Boundary-Aware Mucosal Refinement

Reverse Attention is the defining algorithmic innovation of PraNet. Conventional attention mechanisms amplify high-confidence foreground regions. However, polyp bodies are visually salient and easily segmented; the primary clinical challenge is identifying the **lesion boundary** (demarcation margin) where dysplastic tissue transitions into normal mucosal folds.

```
       Saliency Map S_{i+1} [B, 1, H_{prev}, W_{prev}]
                 │
                 ▼
       Bilinear Interpolate to (H_i, W_i)
                 │
                 ▼
          Sigmoid: σ(S)
                 │
                 ▼
     Inversion: A_{rev} = 1.0 - σ(S)
                 │
                 │                Feature Map r_i [B, C, H_i, W_i]
                 │                               │
                 ▼                               ▼
       Broadcasting & Elementwise Multiplication: r_i ⊙ A_{rev}
                                 │
                                 ▼
                     conv1: BasicConv2d(C, C, 3, p=1)
                                 │
                                 ▼
                     conv2: BasicConv2d(C, C, 3, p=1)
                                 │
                                 ▼
                     CBAM Attention (Channel + Spatial)
                                 │
                                 ▼
                     conv_out: Conv2d(C, 1, 1)
                                 │
                                 ▼
                   Refined Saliency Map S_i [B, 1, H_i, W_i]
```

### 5.1 Mathematical Principle of Interior Erasure

Let $S \in \mathbb{R}^{B \times 1 \times H \times W}$ be the preceding continuous saliency map logits. The reverse attention operator $A_{rev}$ is defined as:
$$A_{rev}(x, y) = 1.0 - \sigma(S(x, y)) = 1.0 - \frac{1}{1 + e^{-S(x, y)}} = \frac{e^{-S(x, y)}}{1 + e^{-S(x, y)}}$$

Behavior across lesion topography:
- **Interior Polyp Core ($S \gg 0$)**: $\sigma(S) \to 1.0 \implies A_{rev} \to 0.0$.
  The feature representation inside the polyp is multiplied by 0, **completely erasing the interior**.
- **Distant Normal Mucosa ($S \ll 0$)**: $\sigma(S) \to 0.0 \implies A_{rev} \to 1.0$.
  Although $A_{rev} \approx 1$, the feature activations $r_i$ in distant background have low response, keeping activations minimal.
- **Lesion Demarcation Margin ($S \approx 0$)**: $\sigma(S) \approx 0.5 \implies A_{rev} \approx 0.5$.
  Because the interior is erased and background is uninformative, the network's optimization gradient is concentrated **exclusively on the mucosal boundary band**.

### 5.2 Convolutional Block Attention Module (CBAM) Details

Inside each Reverse Attention module in `pranet_resnet101.py` and `Combo1_ChakraNet_Focal.ipynb`, features are modulated by a CBAM block:

1. **Channel Attention ($M_c$)**:
   - Aggregates spatial information via dual pooling:
     $$F_{avg} = \text{AdaptiveAvgPool2d}(x) \in \mathbb{R}^{B \times C \times 1 \times 1}$$
     $$F_{max} = \text{AdaptiveMaxPool2d}(x) \in \mathbb{R}^{B \times C \times 1 \times 1}$$
   - Shared MLP with reduction ratio $r = 8$:
     `fc` = `Linear(C, C//8, bias=False)` $\to$ `ReLU` $\to$ `Linear(C//8, C, bias=False)`.
   - Attention Map:
     $$M_c(x) = \sigma(\text{fc}(F_{avg}) + \text{fc}(F_{max})) \in \mathbb{R}^{B \times C \times 1 \times 1}$$
   - Feature Modulation: $x' = x \odot M_c(x)$.
   - Parameters: $2 \times (C \times (C/r)) = 2 \cdot C^2 / r$.
     For $C = 48, r = 8$: $2 \times 48 \times 6 = \mathbf{576}$ parameters.
     For $C = 64, r = 8$: $2 \times 64 \times 8 = \mathbf{1024}$ parameters.

2. **Spatial Attention ($M_s$)**:
   - Aggregates channel information via mean and max projections:
     $$F_{s\_mean} = \text{mean}(x', \text{dim}=1, \text{keepdim}=\text{True}) \in \mathbb{R}^{B \times 1 \times H' \times W'}$$
     $$F_{s\_max} = \max(x', \text{dim}=1, \text{keepdim}=\text{True})[0] \in \mathbb{R}^{B \times 1 \times H' \times W'}$$
   - Concatenation: $[F_{s\_mean}, F_{s\_max}] \in \mathbb{R}^{B \times 2 \times H' \times W'}$.
   - Spatial Convolution: `Conv2d(2, 1, kernel_size=7, padding=3, bias=False)`.
     $$M_s(x') = \sigma(\text{Conv}_{7\times 7}([F_{s\_mean}, F_{s\_max}])) \in \mathbb{R}^{B \times 1 \times H' \times W'}$$
   - Parameters: $2 \times 1 \times 7 \times 7 = \mathbf{98}$ parameters.
   - Final Output: $x'' = x' \odot M_s(x')$.

3. **Total Reverse Attention Parameters**:
   - `conv1`: $C \times C \times 9 + 2C$. (For $C=48$: 20,832; for $C=64$: 36,992)
   - `conv2`: $C \times C \times 9 + 2C$. (For $C=48$: 20,832; for $C=64$: 36,992)
   - `attn` (CBAM): $2 \cdot C^2 / 8 + 98$. (For $C=48$: 674; for $C=64$: 1,122)
   - `conv_out`: $C \times 1 + 1$. (For $C=48$: 49; for $C=64$: 65)
   - Total per RA: $\mathbf{42,387}$ ($C=48$); $\mathbf{75,171}$ ($C=64$).
   - Total across 4 RA stages: $\mathbf{169,548}$ ($C=48$); $\mathbf{300,684}$ ($C=64$).

### 5.3 Top-Down Cascaded Reverse Attention Sequence

The Reverse Attention operates in a top-down, coarse-to-fine hierarchy across all 4 RFB levels:

```
Stage 4 (Coarsest, H/32):
  s_g [B, 1, H/8, W/8]  ──► Downsample to (H/32, W/32) ──┐
  r4  [B, C, H/32, W/32] ────────────────────────────────┼──► RA4 ──► s_4 [B, 1, H/32, W/32] (lateral_map_5)
                                                                       │
Stage 3 (Mid-Coarse, H/16):                                            ▼
  s_4 [B, 1, H/32, W/32] ─► Upsample (x2) to (H/16, W/16) ─────────────┐
  r3  [B, C, H/16, W/16] ──────────────────────────────────────────────┼──► RA3 ──► s_3 [B, 1, H/16, W/16] (lateral_map_4)
                                                                       │
Stage 2 (Mid-Fine, H/8):                                               ▼
  s_3 [B, 1, H/16, W/16] ─► Upsample (x2) to (H/8, W/8) ───────────────┐
  r2  [B, C, H/8, W/8]   ──────────────────────────────────────────────┼──► RA2 ──► s_2 [B, 1, H/8, W/8]   (lateral_map_3)
                                                                       │
Stage 1 (Finest Mucosal, H/4):                                         ▼
  s_2 [B, 1, H/8, W/8]   ─► Upsample (x2) to (H/4, W/4) ───────────────┐
  r1  [B, C, H/4, W/4]   ──────────────────────────────────────────────┴──► RA1 ──► s_1 [B, 1, H/4, W/4]   (lateral_map_2)
                                                                                    │
                                                                                    ▼
                                                                     Upsample (x4) to Full Frame (H, W)
                                                                                    │
                                                                                    ▼
                                                                     Final Output Logits [B, 1, H, W]
```

### 5.4 Deep Supervision and Lateral Maps
During training, PraNet returns 5 deep supervision prediction maps, all upsampled bilinearly to the full resolution $(H, W)$:
1. `lateral_map_1` (`s_g_up`): Upsampled from coarse global saliency $S_g$ ($H/8 \to H$).
2. `lateral_map_5` (`s_4_up`): Upsampled from RA Stage 4 $S_4$ ($H/32 \to H$).
3. `lateral_map_4` (`s_3_up`): Upsampled from RA Stage 3 $S_3$ ($H/16 \to H$).
4. `lateral_map_3` (`s_2_up`): Upsampled from RA Stage 2 $S_2$ ($H/8 \to H$).
5. `lateral_map_2` (`out` / `s_1_up`): Upsampled from RA Stage 1 $S_1$ ($H/4 \to H$).

Total Multi-Stage Loss:
$$\mathcal{L}_{total} = \mathcal{L}(S_1, Y) + \mathcal{L}(S_2, Y) + \mathcal{L}(S_3, Y) + \mathcal{L}(S_4, Y) + \mathcal{L}(S_g, Y)$$
where $\mathcal{L} = \mathcal{L}_{BCE} + \mathcal{L}_{IoU}$ (or $\text{DiceFocalLoss}$).

---

## 6. Complete Tensor Shape Trace: Forward Pass Matrix

The table below traces the exact dimensions of every tensor throughout the forward pass under both benchmark resolutions ($352 \times 352$ standard benchmark, and $384 \times 384$ production ROI crop):

### 6.1 PraNet ResNet-101 / ResNet-50 Tensor Flow

| Module / Operation | Operation Description | Input Tensor Shape ($352 \times 352$) | Output Tensor Shape ($352 \times 352$) | Input Tensor Shape ($384 \times 384$) | Output Tensor Shape ($384 \times 384$) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Input** | RGB Endoscopic Image | — | `[B, 3, 352, 352]` | — | `[B, 3, 384, 384]` |
| `conv1` | Conv2d(3, 64, 7x7, s=2, p=3) | `[B, 3, 352, 352]` | `[B, 64, 176, 176]` | `[B, 3, 384, 384]` | `[B, 64, 192, 192]` |
| `bn1` + `relu` | Normalization & Activation | `[B, 64, 176, 176]` | `[B, 64, 176, 176]` | `[B, 64, 192, 192]` | `[B, 64, 192, 192]` |
| `maxpool` | MaxPool2d(3x3, s=2, p=1) | `[B, 64, 176, 176]` | `[B, 64, 88, 88]` | `[B, 64, 192, 192]` | `[B, 64, 96, 96]` |
| `layer1` (`enc1`) | 3 Bottleneck blocks (stride 1) | `[B, 64, 88, 88]` | `[B, 256, 88, 88]` | `[B, 64, 96, 96]` | `[B, 256, 96, 96]` |
| `layer2` (`enc2`) | 4 Bottleneck blocks (stride 2) | `[B, 256, 88, 88]` | `[B, 512, 44, 44]` | `[B, 256, 96, 96]` | `[B, 512, 48, 48]` |
| `layer3` (`enc3`) | 23 (or 6) Bottlenecks (stride 2) | `[B, 512, 44, 44]` | `[B, 1024, 22, 22]` | `[B, 512, 48, 48]` | `[B, 1024, 24, 24]` |
| `layer4` (`enc4`) | 3 Bottleneck blocks (stride 2) | `[B, 1024, 22, 22]` | `[B, 2048, 11, 11]` | `[B, 1024, 24, 24]` | `[B, 2048, 12, 12]` |
| `rfb1` | Receptive Field Block 1 | `[B, 256, 88, 88]` | `[B, C, 88, 88]` | `[B, 256, 96, 96]` | `[B, C, 96, 96]` |
| `rfb2` | Receptive Field Block 2 | `[B, 512, 44, 44]` | `[B, C, 44, 44]` | `[B, 512, 48, 48]` | `[B, C, 48, 48]` |
| `rfb3` | Receptive Field Block 3 | `[B, 1024, 22, 22]` | `[B, C, 22, 22]` | `[B, 1024, 24, 24]` | `[B, C, 24, 24]` |
| `rfb4` | Receptive Field Block 4 | `[B, 2048, 11, 11]` | `[B, C, 11, 11]` | `[B, 2048, 12, 12]` | `[B, C, 12, 12]` |
| `r3_up` | Bilinear Upsample (x2) | `[B, C, 22, 22]` | `[B, C, 44, 44]` | `[B, C, 24, 24]` | `[B, C, 48, 48]` |
| `r4_up` | Bilinear Upsample (x4) | `[B, C, 11, 11]` | `[B, C, 44, 44]` | `[B, C, 12, 12]` | `[B, C, 48, 48]` |
| `r1_down` (4-in PPD) | Bilinear Downsample (x0.5) | `[B, C, 88, 88]` | `[B, C, 44, 44]` | `[B, C, 96, 96]` | `[B, C, 48, 48]` |
| `ppd_cat` | Concatenate features | — | `[B, 3C or 4C, 44, 44]` | — | `[B, 3C or 4C, 48, 48]` |
| `ppd_conv` | BasicConv2d(3C/4C, C, 3, p=1) | `[B, 3C/4C, 44, 44]` | `[B, C, 44, 44]` | `[B, 3C/4C, 48, 48]` | `[B, C, 48, 48]` |
| `ppd_out` (`s_g`) | Conv2d(C, 1, 1) | `[B, C, 44, 44]` | **`[B, 1, 44, 44]`** | `[B, C, 48, 48]` | **`[B, 1, 48, 48]`** |
| `s_g_r4` | Bilinear Downsample (x0.25) | `[B, 1, 44, 44]` | `[B, 1, 11, 11]` | `[B, 1, 48, 48]` | `[B, 1, 12, 12]` |
| `ra4` (`s_4`) | Reverse Attention Stage 4 | `feat: [B, C, 11, 11]`, `sal: [B, 1, 11, 11]` | **`[B, 1, 11, 11]`** | `feat: [B, C, 12, 12]`, `sal: [B, 1, 12, 12]` | **`[B, 1, 12, 12]`** |
| `s_4_r3` | Bilinear Upsample (x2) | `[B, 1, 11, 11]` | `[B, 1, 22, 22]` | `[B, 1, 12, 12]` | `[B, 1, 24, 24]` |
| `ra3` (`s_3`) | Reverse Attention Stage 3 | `feat: [B, C, 22, 22]`, `sal: [B, 1, 22, 22]` | **`[B, 1, 22, 22]`** | `feat: [B, C, 24, 24]`, `sal: [B, 1, 24, 24]` | **`[B, 1, 24, 24]`** |
| `s_3_r2` | Bilinear Upsample (x2) | `[B, 1, 22, 22]` | `[B, 1, 44, 44]` | `[B, 1, 24, 24]` | `[B, 1, 48, 48]` |
| `ra2` (`s_2`) | Reverse Attention Stage 2 | `feat: [B, C, 44, 44]`, `sal: [B, 1, 44, 44]` | **`[B, 1, 44, 44]`** | `feat: [B, C, 48, 48]`, `sal: [B, 1, 48, 48]` | **`[B, 1, 48, 48]`** |
| `s_2_r1` | Bilinear Upsample (x2) | `[B, 1, 44, 44]` | `[B, 1, 88, 88]` | `[B, 1, 48, 48]` | `[B, 1, 96, 96]` |
| `ra1` (`s_1`) | Reverse Attention Stage 1 | `feat: [B, C, 88, 88]`, `sal: [B, 1, 88, 88]` | **`[B, 1, 88, 88]`** | `feat: [B, C, 96, 96]`, `sal: [B, 1, 96, 96]` | **`[B, 1, 96, 96]`** |
| `out` | Final Bilinear Upsample (x4) | `[B, 1, 88, 88]` | **`[B, 1, 352, 352]`** | `[B, 1, 96, 96]` | **`[B, 1, 384, 384]`** |

*(Where $C = 48$ in `pranet_resnet101.py` and $C = 64$ in Max-Spec).*

---

### 6.2 ChakraNetMicroRefiner (ViT-Large) Tensor Flow

In `src/models/chakranet_segmenter.py`, the model strictly requires $384 \times 384$ input due to hardcoded positional embeddings:

| Module / Operation | Input Tensor Shape | Output Tensor Shape | Operation Description |
| :--- | :--- | :--- | :--- |
| **Input Frame** | — | `[B, 3, 384, 384]` | Padded square letterbox crop normalized with ImageNet statistics |
| `patch_embed` | `[B, 3, 384, 384]` | `[B, 576, 1024]` | Conv2d(3, 1024, k=16, s=16) $\to$ Flatten $\to$ Transpose ($24 \times 24 = 576$ patches) |
| `cls_token` concat | `[B, 576, 1024]` | `[B, 577, 1024]` | Prepend learnable classification token $[1, 1, 1024]$ |
| `pos_embed` add | `[B, 577, 1024]` | `[B, 577, 1024]` | Elementwise addition of learned spatial positional embeddings |
| 24 Transformer Blocks | `[B, 577, 1024]` | `[B, 577, 1024]` | Multi-Head Self-Attention (16 heads) + MLP ($1024 \to 4096 \to 1024$) |
| Strip CLS token | `[B, 577, 1024]` | `[B, 576, 1024]` | `features[:, 1:]` drops the 0-th token |
| Spatial Grid Reshape | `[B, 576, 1024]` | `[B, 1024, 24, 24]` | `.transpose(1, 2).contiguous().view(B, 1024, 24, 24)` |
| `decode_head[0]` | `[B, 1024, 24, 24]` | `[B, 256, 96, 96]` | `ConvTranspose2d(1024, 256, kernel_size=4, stride=4)` (4x upsample) |
| `decode_head[1]` | `[B, 256, 96, 96]` | `[B, 256, 96, 96]` | `BatchNorm2d(256)` |
| `decode_head[2]` | `[B, 256, 96, 96]` | `[B, 256, 96, 96]` | `ReLU(inplace=True)` |
| `decode_head[3]` | `[B, 256, 96, 96]` | `[B, 64, 384, 384]` | `ConvTranspose2d(256, 64, kernel_size=4, stride=4)` (4x upsample) |
| `decode_head[4]` | `[B, 64, 384, 384]` | `[B, 64, 384, 384]` | `BatchNorm2d(64)` |
| `decode_head[5]` | `[B, 64, 384, 384]` | `[B, 64, 384, 384]` | `ReLU(inplace=True)` |
| `decode_head[6]` | `[B, 64, 384, 384]` | **`[B, 1, 384, 384]`** | `Conv2d(64, 1, kernel_size=3, padding=1)` $\to$ Raw continuous logits |

---

## 7. Master Parameter Count Census (Weights, Biases & Buffers)

Below is the definitive census comparing the three model variations:

| Structural Component | PraNet ResNet-50 ($C=48$)<br>(`pranet_resnet101.py` / `combo1_best.pth`) | PraNet ResNet-101 ($C=64$)<br>(Combo 1 Max-Spec Notebook) | ChakraNetMicroRefiner<br>(ViT-Large + Head) |
| :--- | :---: | :---: | :---: |
| **Backbone Feature Extractor** | 23,508,032 (ResNet-50) | 42,500,160 (ResNet-101) | 304,715,752 (ViT-Large 384) |
| — Stem (`conv1` + `bn1`) | 9,536 | 9,536 | 787,456 (`patch_embed`) + 591,872 (`pos`+`cls`) |
| — Layer 1 (Stage 1) | 215,808 | 215,808 | 302,309,376 (Blocks 1–24) |
| — Layer 2 (Stage 2) | 1,219,584 | 1,219,584 | — |
| — Layer 3 (Stage 3) | 7,098,368 | 26,090,496 | — |
| — Layer 4 (Stage 4) | 14,964,736 | 14,964,736 | 2,048 (`norm`) + 1,025,000 (`head` unused) |
| **Receptive Field Blocks (Neck)** | **1,784,448** | **2,760,192** | **0** (None) |
| — RFB-1 (Layer 1 $\to C$) | 277,152 | 464,768 | — |
| — RFB-2 (Layer 2 $\to C$) | 338,592 | 546,688 | — |
| — RFB-3 (Layer 3 $\to C$) | 461,472 | 710,528 | — |
| — RFB-4 (Layer 4 $\to C$) | 707,232 | 1,038,208 | — |
| **Parallel Partial Decoder (PPD)** | **83,089** (4-input) | **110,785** (3-input) | **0** (None) |
| — `ppd_conv` | 83,040 ($192 \to 48$) | 110,720 ($192 \to 64$) | — |
| — `ppd_out` / `ppd_pred` | 49 ($48 \to 1$) | 65 ($64 \to 1$) | — |
| **Reverse Attention Cascade** | **169,548** | **300,684** | **0** (None) |
| — RA-4 ($r_4 \to S_4$) | 42,387 | 75,171 | — |
| — RA-3 ($r_3 \to S_3$) | 42,387 | 75,171 | — |
| — RA-2 ($r_2 \to S_2$) | 42,387 | 75,171 | — |
| — RA-1 ($r_1 \to S_1$) | 42,387 | 75,171 | — |
| **TransposeConv Decode Head** | **0** (None) | **0** (None) | **4,457,985** (7 modules) |
| — Stage 1 TransposeConv ($1024 \to 256$) | — | — | 4,194,560 + 512 (BN) |
| — Stage 2 TransposeConv ($256 \to 64$) | — | — | 262,208 + 128 (BN) |
| — Final Output Conv ($64 \to 1$) | — | — | 577 |
| **Total Trainable Parameters** | **25,545,117** | **45,671,821** | **309,173,737** |
| **Total State Dict Elements (+ Buffers)** | **25,604,983** | **45,786,170** | **309,174,379** |

---

## 8. Draft Inline Code Annotations for `chakranet_segmenter.py` & `pranet_resnet101.py`

Below are the exact draft annotations structuring both files into rigorous **Body**, **Neck**, and **Decoder** demarcations with explicit tensor shape transformations:

### 8.1 Annotations for `src/models/chakranet_segmenter.py`

```python
# ==============================================================================
# SECTION A: LEGACY PRANET CNN COMPONENTS (NECK & BOUNDARY DECODER)
# ==============================================================================

class BasicConv2d(nn.Module):
    """
    [ATOMIC BLOCK] 2D Convolution with Batch Normalization and ReLU Activation.
    Tensor shape: [B, in_planes, H, W] -> [B, out_planes, H', W']
    where H' = floor((H + 2*padding - dilation*(kernel_size-1) - 1)/stride + 1)
    """
    def __init__(self, in_planes, out_planes, kernel_size, stride=1, padding=0, dilation=1):
        super(BasicConv2d, self).__init__()
        # Conv2d weights: [out_planes, in_planes, k_h, k_w] (bias=False for BN stability)
        self.conv = nn.Conv2d(
            in_planes, out_planes,
            kernel_size=kernel_size, stride=stride,
            padding=padding, dilation=dilation, bias=False
        )
        self.bn = nn.BatchNorm2d(out_planes) # Running mean/var buffers: 2 * out_planes
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        # Tensor shape: [B, in_planes, H, W] -> [B, out_planes, H', W']
        return self.relu(self.bn(self.conv(x)))


class RFBBlock(nn.Module):
    """
    [NECK] Receptive Field Block (RFB) for Multi-Scale Endoscopic Context Extraction.
    Extracts multi-scale receptive fields (ERF = 1, 7, 11, 15) across 4 parallel branches.
    Tensor shape: [B, in_channel, H', W'] -> [B, out_channel, H', W']
    Total parameters: 5 * in_channel * out_channel + 93 * out_channel^2 + 30 * out_channel
    """
    def __init__(self, in_channel, out_channel):
        super(RFBBlock, self).__init__()
        self.relu = nn.ReLU(True)
        # Branch 0: 1x1 local projection | Tensor shape: [B, in_channel, H', W'] -> [B, out_channel, H', W']
        self.branch0 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
        )
        # Branch 1: Factorized 3x3 + dilated (d=3) | ERF = 7 | Tensor shape: [B, in_channel, H', W'] -> [B, out_channel, H', W']
        self.branch1 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 3), padding=(0, 1)),
            BasicConv2d(out_channel, out_channel, kernel_size=(3, 1), padding=(1, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=3, dilation=3)
        )
        # Branch 2: Factorized 5x5 + dilated (d=5) | ERF = 11 | Tensor shape: [B, in_channel, H', W'] -> [B, out_channel, H', W']
        self.branch2 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 5), padding=(0, 2)),
            BasicConv2d(out_channel, out_channel, kernel_size=(5, 1), padding=(2, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=5, dilation=5)
        )
        # Branch 3: Factorized 7x7 + dilated (d=7) | ERF = 15 | Tensor shape: [B, in_channel, H', W'] -> [B, out_channel, H', W']
        self.branch3 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 7), padding=(0, 3)),
            BasicConv2d(out_channel, out_channel, kernel_size=(7, 1), padding=(3, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=7, dilation=7)
        )
        # Fusion: 36 * out_channel^2 + 2 * out_channel params | Tensor shape: [B, 4*out_channel, H', W'] -> [B, out_channel, H', W']
        self.conv_cat = BasicConv2d(4 * out_channel, out_channel, 3, padding=1)
        # Residual shortcut projection | Tensor shape: [B, in_channel, H', W'] -> [B, out_channel, H', W']
        self.conv_res = BasicConv2d(in_channel, out_channel, 1)

    def forward(self, x):
        # Tensor shape: x is [B, in_channel, H', W']
        x0 = self.branch0(x) # [B, out_channel, H', W']
        x1 = self.branch1(x) # [B, out_channel, H', W']
        x2 = self.branch2(x) # [B, out_channel, H', W']
        x3 = self.branch3(x) # [B, out_channel, H', W']
        # Channel concatenation: [B, 4 * out_channel, H', W']
        x_cat = self.conv_cat(torch.cat((x0, x1, x2, x3), 1)) # -> [B, out_channel, H', W']
        # Elementwise residual addition & activation: [B, out_channel, H', W']
        x = self.relu(x_cat + self.conv_res(x))
        return x


class ReverseAttention(nn.Module):
    """
    [DECODER BLOCK] Reverse Attention (RA) Mucosal Margin Boundary Refinement.
    Erases interior polyp body via A_rev = 1.0 - sigmoid(S) to force focus onto lesion edges.
    Tensor shape: feat [B, in_channel, H', W'] x sal [B, 1, H', W'] -> [B, 1, H', W']
    """
    def __init__(self, in_channel, out_channel):
        super(ReverseAttention, self).__init__()
        # Boundary refinement convolutions
        self.conv1 = BasicConv2d(in_channel, out_channel, 3, padding=1)
        self.conv2 = BasicConv2d(out_channel, out_channel, 3, padding=1)
        self.conv3 = nn.Conv2d(out_channel, 1, 1) # Projection to 1-channel boundary saliency map

    def forward(self, x, saliency_map):
        # Tensor shape: x is [B, in_channel, H', W'], saliency_map is [B, 1, H', W']
        # 1. Reverse Attention Weight: 1.0 - sigmoid(S) -> [B, 1, H', W']
        reverse_weight = 1.0 - torch.sigmoid(saliency_map)
        # 2. Elementwise Interior Eradication: [B, in_channel, H', W'] * [B, in_channel, H', W']
        x = x * reverse_weight.expand_as(x)
        # 3. Boundary Feature Refinement: [B, in_channel, H', W'] -> [B, out_channel, H', W']
        x = self.conv1(x)
        x = self.conv2(x)
        # 4. Saliency Map Logit Projection: [B, out_channel, H', W'] -> [B, 1, H', W']
        out = self.conv3(x)
        return out


# ==============================================================================
# SECTION B: PRODUCTION VISION TRANSFORMER SEGMENTER (CHAKRANET MICROREFINER)
# ==============================================================================

class ChakraNetMicroRefiner(nn.Module):
    """
    [COMPLETE MODEL] Vision Transformer Polyp Segmenter (ChakraTransformer).
    - BODY: ViT-Large (vit_large_patch16_384, 24 blocks, dim=1024) [304,715,752 params]
    - NECK: CLS Strip & 2D Spatial Reshaping [0 params]
    - DECODER: 2-Stage Progressive ConvTranspose2d Head [4,457,985 params]
    Total Parameters: 309,173,737 trainable (309,174,379 in state_dict)
    """
    def __init__(self, channels=32):
        super(ChakraNetMicroRefiner, self).__init__()
        self.mc_dropout = False
        
        # [BODY] Pretrained ViT-Large Backbone
        # Patch projection: Conv2d(3, 1024, k=16, s=16) -> 24x24 = 576 patches + 1 CLS = 577 tokens
        self.backbone = timm.create_model(
            'vit_large_patch16_384', 
            pretrained=True, 
            img_size=384, 
            drop_rate=0.1, 
            attn_drop_rate=0.1
        )
        self.embed_dim = self.backbone.embed_dim # 1024
        
        # [DECODER] 2-Stage Progressive Transposed Convolution Head (16x Spatial Upscaling)
        # Input: [B, 1024, 24, 24] -> Output: [B, 1, 384, 384]
        self.decode_head = nn.Sequential(
            # Stage 1: 4x Upscaling (24x24 -> 96x96), channels: 1024 -> 256
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4), # [B, 1024, 24, 24] -> [B, 256, 96, 96]
            nn.BatchNorm2d(256),                                              # [B, 256, 96, 96] -> [B, 256, 96, 96]
            nn.ReLU(inplace=True),
            # Stage 2: 4x Upscaling (96x96 -> 384x384), channels: 256 -> 64
            nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),             # [B, 256, 96, 96] -> [B, 64, 384, 384]
            nn.BatchNorm2d(64),                                               # [B, 64, 384, 384] -> [B, 64, 384, 384]
            nn.ReLU(inplace=True),
            # Final Projection: Channels 64 -> 1 continuous logit map
            nn.Conv2d(64, 1, kernel_size=3, padding=1)                        # [B, 64, 384, 384] -> [B, 1, 384, 384]
        )
        self.drop = nn.Dropout2d(p=0.1)

    def forward(self, x):
        # Input tensor shape: [B, 3, 384, 384]
        B, C, H, W = x.shape
        dropout_active = self.training or self.mc_dropout

        with torch.amp.autocast('cuda' if x.is_cuda else 'cpu'):
            # ------------------------------------------------------------------
            # 1. [BODY] ViT-Large Feature Extraction
            # ------------------------------------------------------------------
            # Tensor shape: [B, 3, 384, 384] -> [B, 577, 1024]
            features = self.backbone.forward_features(x)
            
            # ------------------------------------------------------------------
            # 2. [NECK] Sequence Token Unpacking & Spatial Grid Reshaping
            # ------------------------------------------------------------------
            if features.dim() == 3:
                # Strip CLS token: [B, 577, 1024] -> [B, 576, 1024]
                if features.shape[1] == (H // 16) * (W // 16) + 1:
                    features = features[:, 1:]
                grid_h = H // 16 # 24
                grid_w = W // 16 # 24
                # Transpose & Reshape: [B, 576, 1024] -> [B, 1024, 576] -> [B, 1024, 24, 24]
                features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)

            # Spatial Dropout: [B, 1024, 24, 24] -> [B, 1024, 24, 24]
            if dropout_active:
                features = F.dropout2d(features, p=0.1, training=True)

            # ------------------------------------------------------------------
            # 3. [DECODER] 2-Stage Progressive Transpose Convolution
            # ------------------------------------------------------------------
            # Tensor shape: [B, 1024, 24, 24] -> [B, 256, 96, 96] -> [B, 64, 384, 384] -> [B, 1, 384, 384]
            logits = self.decode_head(features)

            # Fallback interpolation guard (noop when input is 384x384)
            if logits.shape[2:] != (H, W):
                logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)

        # Output continuous mask logits: [B, 1, 384, 384]
        return logits
```

---

### 8.2 Annotations for `src/models/pranet_resnet101.py`

```python
# ==============================================================================
# PRANET RESNET-101 / RESNET-50 POLYPE SEGMENTER FORWARD PASS ANNOTATION
# ==============================================================================

class PraNetResNet101(nn.Module):
    """
    [COMPLETE MODEL] Parallel Reverse Attention Network (PraNet).
    - BODY: ResNet-50 backbone (enc0..enc4) [23,508,032 params]
    - NECK: 4-Stage Receptive Field Blocks (rfb1..rfb4) [1,784,448 params]
    - DECODER (STAGE 1): Parallel Partial Decoder (PPD) [83,089 params]
    - DECODER (STAGE 2): 4-Stage Reverse Attention Cascade (ra4..ra1) [169,548 params]
    Total Parameters: 25,545,117 trainable (25,604,983 in state_dict)
    """
    def forward(self, x):
        # Input tensor shape: [B, 3, H, W] (e.g., [B, 3, 352, 352] or [B, 3, 384, 384])
        h, w = x.shape[2], x.shape[3]
        dropout_active = self.training or self.mc_dropout_enabled

        # ----------------------------------------------------------------------
        # 1. [BODY] ResNet Feature Hierarchy Extraction
        # ----------------------------------------------------------------------
        # Stem (conv1, bn1, relu, maxpool): [B, 3, H, W] -> [B, 64, H/4, W/4]
        x0 = self.enc0(x)
        # Layer 1 (res2): [B, 64, H/4, W/4] -> [B, 256, H/4, W/4]
        e1 = self.enc1(x0)
        # Layer 2 (res3): [B, 256, H/4, W/4] -> [B, 512, H/8, W/8]
        e2 = self.enc2(e1)
        # Layer 3 (res4): [B, 512, H/8, W/8] -> [B, 1024, H/16, W/16]
        e3 = self.enc3(e2)
        # Layer 4 (res5): [B, 1024, H/16, W/16] -> [B, 2048, H/32, W/32]
        e4 = self.enc4(e3)

        # ----------------------------------------------------------------------
        # 2. [NECK] Multi-Scale Context Compression via RFB Blocks
        # ----------------------------------------------------------------------
        # RFB-1: [B, 256,  H/4,  W/4]  -> [B, C, H/4,  W/4]   (where C = 48)
        r1 = self.rfb1(e1)
        # RFB-2: [B, 512,  H/8,  W/8]  -> [B, C, H/8,  W/8]
        r2 = self.rfb2(e2)
        # RFB-3: [B, 1024, H/16, W/16] -> [B, C, H/16, W/16]
        r3 = self.rfb3(e3)
        # RFB-4: [B, 2048, H/32, W/32] -> [B, C, H/32, W/32]
        r4 = self.rfb4(e4)

        if dropout_active:
            r1, r2, r3, r4 = self.drop(r1), self.drop(r2), self.drop(r3), self.drop(r4)

        # ----------------------------------------------------------------------
        # 3. [DECODER STAGE 1] Parallel Partial Decoder (PPD) Global Localization
        # ----------------------------------------------------------------------
        sz2 = r2.shape[2:] # Spatial anchor: (H/8, W/8)
        # Bilinear alignment of multi-stage features to H/8 anchor resolution:
        r1_down = F.interpolate(r1, size=sz2, mode='bilinear', align_corners=False) # [B, C, H/4,  W/4]  -> [B, C, H/8, W/8]
        r3_up   = F.interpolate(r3, size=sz2, mode='bilinear', align_corners=False) # [B, C, H/16, W/16] -> [B, C, H/8, W/8]
        r4_up   = F.interpolate(r4, size=sz2, mode='bilinear', align_corners=False) # [B, C, H/32, W/32] -> [B, C, H/8, W/8]
        
        # Concatenate 4 stages: [B, 4*C, H/8, W/8] = [B, 192, H/8, W/8]
        ppd_cat = torch.cat([r1_down, r2, r3_up, r4_up], dim=1)
        # Fuse channels: [B, 192, H/8, W/8] -> [B, 48, H/8, W/8]
        ppd_feat = self.ppd_conv(ppd_cat)
        # Predict coarse global saliency map S_g: [B, 48, H/8, W/8] -> [B, 1, H/8, W/8]
        s_g = self.ppd_out(ppd_feat)

        # ----------------------------------------------------------------------
        # 4. [DECODER STAGE 2] Cascaded Top-Down Reverse Attention Boundary Refinement
        # ----------------------------------------------------------------------
        # Stage 4: Downsample S_g to r4 grid (H/32, W/32), refine boundary:
        # Tensor shape: s_g [B, 1, H/8, W/8] -> [B, 1, H/32, W/32]
        s_g_r4 = F.interpolate(s_g, size=r4.shape[2:], mode='bilinear', align_corners=False)
        # RA-4: feat [B, C, H/32, W/32] x sal [B, 1, H/32, W/32] -> [B, 1, H/32, W/32]
        s_4 = self.ra4(r4, s_g_r4) # lateral_map_5

        # Stage 3: Upsample S_4 to r3 grid (H/16, W/16), refine boundary:
        # Tensor shape: s_4 [B, 1, H/32, W/32] -> [B, 1, H/16, W/16]
        s_4_r3 = F.interpolate(s_4, size=r3.shape[2:], mode='bilinear', align_corners=False)
        # RA-3: feat [B, C, H/16, W/16] x sal [B, 1, H/16, W/16] -> [B, 1, H/16, W/16]
        s_3 = self.ra3(r3, s_4_r3) # lateral_map_4

        # Stage 2: Upsample S_3 to r2 grid (H/8, W/8), refine boundary:
        # Tensor shape: s_3 [B, 1, H/16, W/16] -> [B, 1, H/8, W/8]
        s_3_r2 = F.interpolate(s_3, size=r2.shape[2:], mode='bilinear', align_corners=False)
        # RA-2: feat [B, C, H/8, W/8] x sal [B, 1, H/8, W/8] -> [B, 1, H/8, W/8]
        s_2 = self.ra2(r2, s_3_r2) # lateral_map_3

        # Stage 1: Upsample S_2 to r1 grid (H/4, W/4), extract fine mucosal margin:
        # Tensor shape: s_2 [B, 1, H/8, W/8] -> [B, 1, H/4, W/4]
        s_2_r1 = F.interpolate(s_2, size=r1.shape[2:], mode='bilinear', align_corners=False)
        # RA-1: feat [B, C, H/4, W/4] x sal [B, 1, H/4, W/4] -> [B, 1, H/4, W/4]
        s_1 = self.ra1(r1, s_2_r1) # lateral_map_2

        # ----------------------------------------------------------------------
        # 5. Full-Resolution Upsampling & Deep Supervision Return
        # ----------------------------------------------------------------------
        # Final output logits: [B, 1, H/4, W/4] -> [B, 1, H, W]
        out = F.interpolate(s_1, size=(h, w), mode='bilinear', align_corners=False)

        if self.training:
            # Upsample intermediate lateral maps for multi-scale deep supervision:
            s_g_up = F.interpolate(s_g, size=(h, w), mode='bilinear', align_corners=False) # lateral_map_1
            s_4_up = F.interpolate(s_4, size=(h, w), mode='bilinear', align_corners=False) # lateral_map_5
            s_3_up = F.interpolate(s_3, size=(h, w), mode='bilinear', align_corners=False) # lateral_map_4
            s_2_up = F.interpolate(s_2, size=(h, w), mode='bilinear', align_corners=False) # lateral_map_3
            return out, s_2_up, s_3_up, s_4_up, s_g_up

        return out
```

---

## 9. Architectural Insights & Failure Forensics

1. **The Ghost Backbone Mismatch**:
   - In `pranet_resnet101.py`, the module is named `PraNetResNet101`, but line 78 hardcodes `models.resnet50(weights=None)`.
   - Forensic tracing of `weights/checkpoints/combo1_best.pth` reveals that the trained model on disk is indeed a ResNet-50 PraNet with 25.55M trainable parameters and 754 state_dict keys.
   - The original Max-Spec ResNet-101 design from `notebooks/combos/Combo1_ChakraNet_Focal.ipynb` (45.67M params) was designed for multi-GPU training but downscaled to ResNet-50 during local execution on 4GB RTX 3050 hardware.

2. **The Key Naming Divergence**:
   - In `pranet_resnet101.py`, line 94 declares `self.ppd_out = nn.Conv2d(48, 1, kernel_size=1)`.
   - In `weights/checkpoints/combo1_best.pth`, the identical tensor is named `ppd_pred.weight` and `ppd_pred.bias`.
   - Loading `combo1_best.pth` into `PraNetResNet101` requires aliasing `ppd_pred` to `ppd_out` (or renaming `self.ppd_pred`), after which 100% of the 754 keys load cleanly.

3. **ViT Resolution Inflexibility vs. Fully Convolutional Freedom**:
   - While PraNet's fully convolutional backbone, RFB blocks, PPD, and RA modules adapt dynamically to any input resolution ($352 \times 352$, $384 \times 384$, or arbitrary video frames) via adaptive pooling and bilinear interpolations, `ChakraNetMicroRefiner` crashes on $352 \times 352$ because `vit_large_patch16_384` enforces a strict $384 \times 384$ spatial embedding grid.
