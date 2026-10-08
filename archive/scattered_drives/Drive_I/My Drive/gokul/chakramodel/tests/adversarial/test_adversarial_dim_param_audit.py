"""
Adversarial Mathematical and Dimensional Audit Test Suite
Empirical verification of tensor shapes, layer parameter counts, and mathematical claims.
Targeting:
- docs/ARCHITECTURE_DEEP_DIVE.md
- docs/parameter_mapping.txt
- src/chakra_transformer/transformer_segmenter.py
- src/models/chakranet_segmenter.py
- src/models/pranet_resnet101.py
"""

import json
import math
import sys
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models

def calc_conv2d_out(h_in, k, s=1, p=0, d=1):
    return math.floor((h_in + 2 * p - d * (k - 1) - 1) / s + 1)

def calc_conv_transpose2d_out(h_in, k, s=1, p=0, d=1, out_pad=0):
    return (h_in - 1) * s - 2 * p + d * (k - 1) + out_pad + 1

def rfb_closed_form(ic, oc):
    return 5 * ic * oc + 93 * (oc ** 2) + 30 * oc

def audit_all():
    results = {
        "tensor_shape_checks": {},
        "parameter_formula_checks": {},
        "rfb_formula_checks": {},
        "resnet_conflation_audit": {},
        "checkpoint_param_counts": {},
        "edge_case_prompt_embed_checks": {},
        "yolo_param_audit": {},
        "overall_verdict": "PENDING"
    }

    print("=" * 80)
    print("CHAKRAMODEL MATHEMATICAL AND DIMENSIONAL EMPIRICAL AUDIT")
    print("=" * 80)

    # ------------------------------------------------------------------------
    # 1. TENSOR SHAPES AND FORMULAS
    # ------------------------------------------------------------------------
    print("\n--- 1. AUDITING TENSOR SHAPES AND CONVOLUTION FORMULAS ---")

    # Transpose Conv Stage 1: 24 -> 96 (k=4, s=4, p=0, d=1, out_pad=0)
    s1_calc = calc_conv_transpose2d_out(24, k=4, s=4, p=0, d=1, out_pad=0)
    tconv1 = nn.ConvTranspose2d(1024, 256, kernel_size=4, stride=4, padding=0)
    s1_torch = tconv1(torch.randn(1, 1024, 24, 24)).shape[2]
    print(f"Stage 1 TransposeConv: 24 -> calc={s1_calc}, torch={s1_torch}, expected=96")
    results["tensor_shape_checks"]["stage1_transpose_conv"] = {
        "input": 24, "expected": 96, "formula_result": s1_calc, "torch_result": s1_torch, "pass": (s1_calc == 96 == s1_torch)
    }

    # Transpose Conv Stage 2: 96 -> 384 (k=4, s=4, p=0, d=1, out_pad=0)
    s2_calc = calc_conv_transpose2d_out(96, k=4, s=4, p=0, d=1, out_pad=0)
    tconv2 = nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4, padding=0)
    s2_torch = tconv2(torch.randn(1, 256, 96, 96)).shape[2]
    print(f"Stage 2 TransposeConv: 96 -> calc={s2_calc}, torch={s2_torch}, expected=384")
    results["tensor_shape_checks"]["stage2_transpose_conv"] = {
        "input": 96, "expected": 384, "formula_result": s2_calc, "torch_result": s2_torch, "pass": (s2_calc == 384 == s2_torch)
    }

    # Conv2d Refinement: 384 -> 384 (k=3, s=1, p=1, d=1)
    ref_calc = calc_conv2d_out(384, k=3, s=1, p=1, d=1)
    conv_ref = nn.Conv2d(64, 1, kernel_size=3, padding=1)
    ref_torch = conv_ref(torch.randn(1, 64, 384, 384)).shape[2]
    print(f"Refinement Conv2d: 384 -> calc={ref_calc}, torch={ref_torch}, expected=384")
    results["tensor_shape_checks"]["refinement_conv2d"] = {
        "input": 384, "expected": 384, "formula_result": ref_calc, "torch_result": ref_torch, "pass": (ref_calc == 384 == ref_torch)
    }

    # ViT PatchEmbed: 384 -> 24 (k=16, s=16, p=0, d=1)
    pe_calc = calc_conv2d_out(384, k=16, s=16, p=0, d=1)
    conv_pe = nn.Conv2d(3, 1024, kernel_size=16, stride=16)
    pe_torch = conv_pe(torch.randn(1, 3, 384, 384)).shape[2]
    print(f"ViT PatchEmbed Conv2d: 384 -> calc={pe_calc}, torch={pe_torch}, expected=24")
    results["tensor_shape_checks"]["patch_embed_conv2d"] = {
        "input": 384, "expected": 24, "formula_result": pe_calc, "torch_result": pe_torch, "pass": (pe_calc == 24 == pe_torch)
    }

    # ------------------------------------------------------------------------
    # 2. PARAMETER CALCULATION VALIDITY
    # ------------------------------------------------------------------------
    print("\n--- 2. AUDITING LAYER PARAMETER COUNTS ---")

    # A. ViT PatchEmbed:
    # 3 * 1024 * 16 * 16 + 1024 = 787,456
    pe_weight = 3 * 1024 * 16 * 16
    pe_bias = 1024
    pe_total = pe_weight + pe_bias
    conv_pe_actual = sum(p.numel() for p in conv_pe.parameters())
    print(f"PatchEmbed: formula={pe_total} (w={pe_weight}, b={pe_bias}), actual={conv_pe_actual}, claimed=787456")
    results["parameter_formula_checks"]["patch_embed"] = {
        "formula": pe_total, "actual": conv_pe_actual, "claimed": 787456, "pass": (pe_total == conv_pe_actual == 787456)
    }

    # B. Transformer Attention QKV:
    # 1024 * 3072 + 3072 = 3,148,800
    qkv_linear = nn.Linear(1024, 3072, bias=True)
    qkv_actual = sum(p.numel() for p in qkv_linear.parameters())
    qkv_calc = 1024 * 3072 + 3072
    print(f"QKV Linear: calc={qkv_calc}, actual={qkv_actual}, claimed=3148800")
    results["parameter_formula_checks"]["attn_qkv"] = {
        "formula": qkv_calc, "actual": qkv_actual, "claimed": 3148800, "pass": (qkv_calc == qkv_actual == 3148800)
    }

    # C. Transformer Attention Proj:
    # 1024 * 1024 + 1024 = 1,049,600
    proj_linear = nn.Linear(1024, 1024, bias=True)
    proj_actual = sum(p.numel() for p in proj_linear.parameters())
    proj_calc = 1024 * 1024 + 1024
    print(f"Proj Linear: calc={proj_calc}, actual={proj_actual}, claimed=1049600")
    results["parameter_formula_checks"]["attn_proj"] = {
        "formula": proj_calc, "actual": proj_actual, "claimed": 1049600, "pass": (proj_calc == proj_actual == 1049600)
    }

    # D. Transformer MLP fc1 & fc2:
    # fc1: 1024 * 4096 + 4096 = 4,198,400
    # fc2: 4096 * 1024 + 1024 = 4,195,328
    fc1_linear = nn.Linear(1024, 4096, bias=True)
    fc1_actual = sum(p.numel() for p in fc1_linear.parameters())
    fc1_calc = 1024 * 4096 + 4096
    fc2_linear = nn.Linear(4096, 1024, bias=True)
    fc2_actual = sum(p.numel() for p in fc2_linear.parameters())
    fc2_calc = 4096 * 1024 + 1024
    print(f"MLP fc1: calc={fc1_calc}, actual={fc1_actual}, claimed=4198400")
    print(f"MLP fc2: calc={fc2_calc}, actual={fc2_actual}, claimed=4195328")
    results["parameter_formula_checks"]["mlp_fc1"] = {
        "formula": fc1_calc, "actual": fc1_actual, "claimed": 4198400, "pass": (fc1_calc == fc1_actual == 4198400)
    }
    results["parameter_formula_checks"]["mlp_fc2"] = {
        "formula": fc2_calc, "actual": fc2_actual, "claimed": 4195328, "pass": (fc2_calc == fc2_actual == 4195328)
    }

    # E. LayerNorm: 1024 * 2 = 2,048
    ln = nn.LayerNorm(1024)
    ln_actual = sum(p.numel() for p in ln.parameters())
    print(f"LayerNorm(1024): actual={ln_actual}, claimed=2048")
    results["parameter_formula_checks"]["layernorm"] = {
        "actual": ln_actual, "claimed": 2048, "pass": (ln_actual == 2048)
    }

    # Total single block:
    single_block_calc = 2048 + qkv_calc + proj_calc + 2048 + fc1_calc + fc2_calc
    print(f"Single Transformer Block Subtotal: calc={single_block_calc}, claimed=12596224")
    results["parameter_formula_checks"]["transformer_block_single"] = {
        "formula": single_block_calc, "claimed": 12596224, "pass": (single_block_calc == 12596224)
    }
    blocks_24_calc = 24 * single_block_calc
    print(f"24 Transformer Blocks Total: calc={blocks_24_calc}, claimed=302309376")
    results["parameter_formula_checks"]["transformer_24_blocks"] = {
        "formula": blocks_24_calc, "claimed": 302309376, "pass": (blocks_24_calc == 302309376)
    }

    # F. Transpose Conv Stage 1:
    # 1024 * 256 * 4 * 4 + 256 = 4,194,560
    tc1_actual = sum(p.numel() for p in tconv1.parameters())
    tc1_calc = 1024 * 256 * 4 * 4 + 256
    print(f"TransposeConv Stage 1: calc={tc1_calc}, actual={tc1_actual}, claimed=4194560")
    results["parameter_formula_checks"]["transpose_conv_s1"] = {
        "formula": tc1_calc, "actual": tc1_actual, "claimed": 4194560, "pass": (tc1_calc == tc1_actual == 4194560)
    }

    # G. Transpose Conv Stage 2:
    # 256 * 64 * 4 * 4 + 64 = 262,208
    tc2_actual = sum(p.numel() for p in tconv2.parameters())
    tc2_calc = 256 * 64 * 4 * 4 + 64
    print(f"TransposeConv Stage 2: calc={tc2_calc}, actual={tc2_actual}, claimed=262208")
    results["parameter_formula_checks"]["transpose_conv_s2"] = {
        "formula": tc2_calc, "actual": tc2_actual, "claimed": 262208, "pass": (tc2_calc == tc2_actual == 262208)
    }

    # H. Refinement Conv2d:
    # 1 * 64 * 3 * 3 + 1 = 577
    ref_actual = sum(p.numel() for p in conv_ref.parameters())
    ref_calc = 1 * 64 * 3 * 3 + 1
    print(f"Refinement Conv2d: calc={ref_calc}, actual={ref_actual}, claimed=577")
    results["parameter_formula_checks"]["conv2d_ref"] = {
        "formula": ref_calc, "actual": ref_actual, "claimed": 577, "pass": (ref_calc == ref_actual == 577)
    }

    # I. BatchNorm2d(256) & BatchNorm2d(64):
    bn256 = nn.BatchNorm2d(256)
    bn64 = nn.BatchNorm2d(64)
    print(f"BN(256) params: {sum(p.numel() for p in bn256.parameters())}, claimed=512")
    print(f"BN(64) params: {sum(p.numel() for p in bn64.parameters())}, claimed=128")

    # Decoder total:
    dec_total_calc = tc1_calc + 512 + tc2_calc + 128 + ref_calc
    print(f"Decode Head Total: calc={dec_total_calc}, claimed=4457985")
    results["parameter_formula_checks"]["decode_head_total"] = {
        "formula": dec_total_calc, "claimed": 4457985, "pass": (dec_total_calc == 4457985)
    }

    # ------------------------------------------------------------------------
    # 3. RFB CLOSED-FORM FORMULA AUDIT
    # ------------------------------------------------------------------------
    print("\n--- 3. AUDITING RFB CLOSED-FORM FORMULA ---")
    sys.path.insert(0, str(Path("M:/chakramodel/src")))
    from models.pranet_resnet101 import RFBBlock, CBAM, ReverseAttention, BasicConv2d

    rfb_tests = [
        (256, 48),
        (512, 48),
        (1024, 48),
        (2048, 48),
        (256, 64),
        (512, 64),
        (1024, 64),
        (2048, 64),
        (64, 32),
        (128, 24),
    ]

    all_rfb_pass = True
    for ic, oc in rfb_tests:
        rfb = RFBBlock(ic, oc)
        actual_p = sum(p.numel() for p in rfb.parameters())
        formula_p = rfb_closed_form(ic, oc)
        match = (actual_p == formula_p)
        if not match:
            all_rfb_pass = False
        print(f"RFBBlock(ic={ic}, oc={oc}): formula={formula_p}, actual={actual_p}, MATCH={match}")
        results["rfb_formula_checks"][f"RFB_{ic}_{oc}"] = {
            "ic": ic, "oc": oc, "formula": formula_p, "actual": actual_p, "pass": match
        }

    print(f"RFB Closed-Form Formula: 5*ic*oc + 93*oc^2 + 30*oc -> ALL MATCH: {all_rfb_pass}")
    results["rfb_formula_checks"]["all_match"] = all_rfb_pass

    # Sum for oc=48 (Module 3A):
    rfb_sum_48 = sum(rfb_closed_form(ic, 48) for ic in [256, 512, 1024, 2048])
    print(f"RFB 1-4 Total (oc=48): calc={rfb_sum_48}, claimed=1784448, MATCH={rfb_sum_48 == 1784448}")

    # Sum for oc=64 (Module 3B):
    rfb_sum_64 = sum(rfb_closed_form(ic, 64) for ic in [256, 512, 1024, 2048])
    print(f"RFB 1-4 Total (oc=64): calc={rfb_sum_64}, claimed=2760192, MATCH={rfb_sum_64 == 2760192}")

    # ------------------------------------------------------------------------
    # 4. CBAM AND REVERSE ATTENTION AUDIT
    # ------------------------------------------------------------------------
    print("\n--- 4. AUDITING REVERSE ATTENTION AND CBAM ---")
    ra_48 = ReverseAttention(48, 48)
    ra_48_actual = sum(p.numel() for p in ra_48.parameters())
    print(f"ReverseAttention(48, 48) with CBAM: actual={ra_48_actual}, claimed=42387, MATCH={ra_48_actual == 42387}")
    results["parameter_formula_checks"]["reverse_attention_48"] = {
        "actual": ra_48_actual, "claimed": 42387, "pass": (ra_48_actual == 42387)
    }

    # PPD conv and out
    ppd_conv = BasicConv2d(192, 48, 3, p=1)
    ppd_out = nn.Conv2d(48, 1, 1)
    ppd_actual = sum(p.numel() for p in ppd_conv.parameters()) + sum(p.numel() for p in ppd_out.parameters())
    print(f"PPD (192->48 + 48->1): actual={ppd_actual}, claimed=83089, MATCH={ppd_actual == 83089}")
    results["parameter_formula_checks"]["ppd_48"] = {
        "actual": ppd_actual, "claimed": 83089, "pass": (ppd_actual == 83089)
    }

    # ------------------------------------------------------------------------
    # 5. RESNET-50 VS RESNET-101 CONFLATION AUDIT
    # ------------------------------------------------------------------------
    print("\n--- 5. AUDITING RESNET-50 VS RESNET-101 IN PRANET ---")
    rn50 = models.resnet50(weights=None)
    rn101 = models.resnet101(weights=None)

    rn50_backbone_p = (
        sum(p.numel() for p in rn50.conv1.parameters()) +
        sum(p.numel() for p in rn50.bn1.parameters()) +
        sum(p.numel() for p in rn50.layer1.parameters()) +
        sum(p.numel() for p in rn50.layer2.parameters()) +
        sum(p.numel() for p in rn50.layer3.parameters()) +
        sum(p.numel() for p in rn50.layer4.parameters())
    )
    rn101_backbone_p = (
        sum(p.numel() for p in rn101.conv1.parameters()) +
        sum(p.numel() for p in rn101.bn1.parameters()) +
        sum(p.numel() for p in rn101.layer1.parameters()) +
        sum(p.numel() for p in rn101.layer2.parameters()) +
        sum(p.numel() for p in rn101.layer3.parameters()) +
        sum(p.numel() for p in rn101.layer4.parameters())
    )

    rn50_layer3_p = sum(p.numel() for p in rn50.layer3.parameters())
    rn101_layer3_p = sum(p.numel() for p in rn101.layer3.parameters())

    print(f"ResNet-50 Backbone params: {rn50_backbone_p} (Claimed in parameter_mapping line 162: 23,508,032)")
    print(f"ResNet-101 Backbone params: {rn101_backbone_p} (Claimed in parameter_mapping line 207: 42,500,160)")
    print(f"ResNet-50 Layer 3 (6 blocks) params: {rn50_layer3_p}")
    print(f"ResNet-101 Layer 3 (23 blocks) params: {rn101_layer3_p}")

    from models.pranet_resnet101 import PraNetResNet101
    pranet_actual = PraNetResNet101(channels=48)
    pranet_total = sum(p.numel() for p in pranet_actual.parameters())
    print(f"Actual PraNetResNet101 class instance total params: {pranet_total} (Claimed: 25,545,117)")

    results["resnet_conflation_audit"] = {
        "resnet50_backbone": rn50_backbone_p,
        "resnet101_backbone": rn101_backbone_p,
        "resnet50_layer3": rn50_layer3_p,
        "resnet101_layer3": rn101_layer3_p,
        "pranet_class_total": pranet_total,
        "pranet_matches_resnet50_combination": (pranet_total == 25545117),
        "conflation_discrepancy": (
            "ARCHITECTURE_DEEP_DIVE.md line 459 claims enc3 has 23 Bottleneck blocks (ResNet-101) with 7,098,368 params. "
            "However, 7,098,368 params is mathematically 6 Bottleneck blocks (ResNet-50). "
            "ResNet-101 layer3 has 23 blocks with 26,090,496 params."
        )
    }

    # ------------------------------------------------------------------------
    # 6. FULL MODEL INSTANTIATION AUDIT
    # ------------------------------------------------------------------------
    print("\n--- 6. AUDITING FULL VIT TRANSFORMER MODELS ---")
    from models.chakranet_segmenter import ChakraNetMicroRefiner
    from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter

    refiner = ChakraNetMicroRefiner()
    refiner_params = sum(p.numel() for p in refiner.parameters())
    print(f"ChakraNetMicroRefiner params: {refiner_params} (Claimed: 309,173,737, MATCH={refiner_params == 309173737})")

    transformer = ChakraTransformerSegmenter(pretrained=False)
    transformer_params = sum(p.numel() for p in transformer.parameters())
    print(f"ChakraTransformerSegmenter params: {transformer_params} (Claimed: 309,175,785, MATCH={transformer_params == 309175785})")

    diff = transformer_params - refiner_params
    print(f"Difference (Prompt Embedding): {diff} params (Expected: 2048, MATCH={diff == 2048})")

    results["checkpoint_param_counts"]["refiner_params"] = refiner_params
    results["checkpoint_param_counts"]["transformer_params"] = transformer_params
    results["checkpoint_param_counts"]["difference"] = diff
    results["checkpoint_param_counts"]["refiner_pass"] = (refiner_params == 309173737)
    results["checkpoint_param_counts"]["transformer_pass"] = (transformer_params == 309175785)

    # ------------------------------------------------------------------------
    # 7. PROMPT EMBEDDING EDGE CASE TESTING
    # ------------------------------------------------------------------------
    print("\n--- 7. ADVERSARIAL EDGE CASE TESTING: PROMPT EMBEDDING ---")
    grid_h = 24
    grid_w = 24
    # Sub-patch bbox < 16 pixels: [0, 0, 15, 15]
    px1 = max(0, int(0 * grid_w / 384))
    py1 = max(0, int(0 * grid_h / 384))
    px2 = min(grid_w, int(15 * grid_w / 384))
    py2 = min(grid_h, int(15 * grid_h / 384))
    mask_sum = (px2 - px1) * (py2 - py1)
    print(f"Sub-patch bbox [0,0,15,15] grid coords: px1={px1}, px2={px2}, py1={py1}, py2={py2} -> Active cells: {mask_sum}")
    results["edge_case_prompt_embed_checks"]["small_bbox_subpatch_empty"] = (mask_sum == 0)
    results["edge_case_prompt_embed_checks"]["floor_vs_ceil_discrepancy"] = (
        "ARCHITECTURE_DEEP_DIVE.md lines 390-391 states px2 = ceil(x2*24/W), but transformer_segmenter.py uses int(x2*grid_w/W) (floor). "
        "For small bboxes < 16px, floor produces px1 == px2, resulting in an empty prompt mask."
    )

    # ------------------------------------------------------------------------
    # 8. CHECKPOINT FORENSIC AUDIT
    # ------------------------------------------------------------------------
    print("\n--- 8. AUDITING ACTUAL CHECKPOINTS ---")
    vit_ckpt_path = Path("M:/chakramodel/weights/checkpoints/chakra_transformer_best.pth")
    combo1_ckpt_path = Path("M:/chakramodel/weights/checkpoints/combo1_best.pth")

    if vit_ckpt_path.exists():
        sd_vit = torch.load(vit_ckpt_path, map_location="cpu", weights_only=False)
        if isinstance(sd_vit, dict) and "state_dict" in sd_vit:
            sd_vit = sd_vit["state_dict"]
        vit_keys = len(sd_vit)
        vit_elems = sum(v.numel() for v in sd_vit.values())
        has_prompt = any("prompt_embedding" in k for k in sd_vit.keys())
        has_cls = any("cls_token" in k for k in sd_vit.keys())
        has_pos = any("pos_embed" in k for k in sd_vit.keys())
        print(f"ViT Checkpoint: keys={vit_keys}, total elements={vit_elems}, prompt_embedding={has_prompt}, cls_token={has_cls}")
        results["checkpoint_param_counts"]["vit_checkpoint"] = {
            "keys": vit_keys,
            "total_elements": vit_elems,
            "has_prompt_embedding": has_prompt,
            "has_cls_token": has_cls,
            "has_pos_embed": has_pos,
            "matches_parameter_mapping_keys": (vit_keys == 312),
            "matches_parameter_mapping_elements": (vit_elems in [309173737, 309174379])
        }

    if combo1_ckpt_path.exists():
        sd_combo1 = torch.load(combo1_ckpt_path, map_location="cpu", weights_only=False)
        if isinstance(sd_combo1, dict) and "state_dict" in sd_combo1:
            sd_combo1 = sd_combo1["state_dict"]
        combo1_keys = len(sd_combo1)
        combo1_elems = sum(v.numel() for v in sd_combo1.values())
        has_cbam = any("attn" in k for k in sd_combo1.keys())
        print(f"Combo1 Checkpoint: keys={combo1_keys}, total elements={combo1_elems}, CBAM keys={has_cbam}")
        results["checkpoint_param_counts"]["combo1_checkpoint"] = {
            "keys": combo1_keys,
            "total_elements": combo1_elems,
            "has_cbam": has_cbam,
            "matches_parameter_mapping_keys": (combo1_keys == 754),
            "matches_parameter_mapping_elements": (combo1_elems == 25604983)
        }

    # ------------------------------------------------------------------------
    # 9. YOLOV8 PARAMETER AUDIT
    # ------------------------------------------------------------------------
    print("\n--- 9. AUDITING YOLOV8N PARAMETERS ---")
    yolo_ckpt = Path("M:/chakramodel/weights/yolo/best.pt")
    if yolo_ckpt.exists():
        from ultralytics import YOLO
        yolo = YOLO(str(yolo_ckpt))
        yolo_params = sum(p.numel() for p in yolo.model.parameters())
        trainable_yolo = sum(p.numel() for p in yolo.model.parameters() if p.requires_grad)
        print(f"YOLOv8n: total params={yolo_params} (Claimed: 3,011,043), trainable={trainable_yolo} (Claimed: 3,011,027)")
        results["yolo_param_audit"] = {
            "total_params": yolo_params,
            "trainable_params": trainable_yolo,
            "claimed_total": 3011043,
            "claimed_trainable": 3011027,
            "pass": (yolo_params == 3011043 and trainable_yolo == 3011027)
        }

    # ------------------------------------------------------------------------
    # FINAL VERDICT
    # ------------------------------------------------------------------------
    all_shapes_pass = all(v["pass"] for v in results["tensor_shape_checks"].values())
    all_params_pass = all(v["pass"] for v in results["parameter_formula_checks"].values())
    all_models_pass = results["checkpoint_param_counts"]["refiner_pass"] and results["checkpoint_param_counts"]["transformer_pass"]
    yolo_pass = results.get("yolo_param_audit", {}).get("pass", True)

    overall_pass = all_shapes_pass and all_params_pass and all_rfb_pass and all_models_pass and yolo_pass
    results["overall_verdict"] = "PASS" if overall_pass else "FAIL"

    print("\n" + "=" * 80)
    print(f"OVERALL EMPIRICAL AUDIT VERDICT: {results['overall_verdict']}")
    print(f"  - Tensor Shapes Rigor: {'PASS' if all_shapes_pass else 'FAIL'}")
    print(f"  - Parameter Formula Rigor: {'PASS' if all_params_pass else 'FAIL'}")
    print(f"  - RFB Closed-Form Formula: {'PASS' if all_rfb_pass else 'FAIL'}")
    print(f"  - Model Instantiations: {'PASS' if all_models_pass else 'FAIL'}")
    print(f"  - YOLOv8 Parameter Counts: {'PASS' if yolo_pass else 'FAIL'}")
    print("=" * 80)

    with open("M:/chakramodel/tests/adversarial_dim_param_audit_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved results to M:/chakramodel/tests/adversarial_dim_param_audit_results.json")

if __name__ == "__main__":
    audit_all()
