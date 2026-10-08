import os
import sys
import torch

workspace = "m:\\chakramodel"
sys.path.insert(0, os.path.join(workspace, "src"))

results = {}

# 1. Inspect chakra_transformer_best.pth
pth_path = os.path.join(workspace, "weights", "chakra_transformer_best.pth")
if os.path.exists(pth_path):
    print("Loading chakra_transformer_best.pth on CPU...")
    ckpt = torch.load(pth_path, map_location="cpu")
    
    is_state_dict = isinstance(ckpt, dict) and not any(k in ckpt for k in ["state_dict", "model_state_dict", "model"])
    if isinstance(ckpt, dict):
        top_keys = list(ckpt.keys())
    else:
        top_keys = str(type(ckpt))
        
    sd = ckpt
    if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
        sd = ckpt["model_state_dict"]
    elif isinstance(ckpt, dict) and "model" in ckpt:
        sd = ckpt["model"]
    elif isinstance(ckpt, dict) and "state_dict" in ckpt:
        sd = ckpt["state_dict"]
        
    keys = list(sd.keys())
    module_keys = [k for k in keys if k.startswith("module.")]
    orig_mod_keys = [k for k in keys if k.startswith("_orig_mod.")]
    plain_keys = [k for k in keys if not k.startswith("module.") and not k.startswith("_orig_mod.")]
    
    total_params = 0
    total_bytes = 0
    dtypes = {}
    for k, v in sd.items():
        if torch.is_tensor(v):
            total_params += v.numel()
            total_bytes += v.numel() * v.element_size()
            dt = str(v.dtype)
            dtypes[dt] = dtypes.get(dt, 0) + v.numel()
            
    # Check loading into ChakraNet
    try:
        from chakranet_segmenter import ChakraNet
        cnet = ChakraNet(img_size=(384, 384), device="cpu")
        
        # Test loading with unstripped keys
        m_raw, u_raw = cnet.model.load_state_dict(sd, strict=False)
        
        # Test loading with stripped keys
        sd_stripped = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in sd.items()}
        m_stripped, u_stripped = cnet.model.load_state_dict(sd_stripped, strict=False)
        
        # Test strict=True with stripped keys
        try:
            cnet.model.load_state_dict(sd_stripped, strict=True)
            strict_error = None
        except Exception as se:
            strict_error = str(se)
            
        chakranet_test = {
            "raw_missing": len(m_raw),
            "raw_unexpected": len(u_raw),
            "stripped_missing": len(m_stripped),
            "stripped_missing_keys": m_stripped,
            "stripped_unexpected": len(u_stripped),
            "stripped_unexpected_keys": u_stripped,
            "strict_error": strict_error
        }
    except Exception as ce:
        chakranet_test = {"error": str(ce)}
        
    results["chakra_transformer_best.pth"] = {
        "file_size_bytes": os.path.getsize(pth_path),
        "is_pure_state_dict": is_state_dict,
        "top_keys_count": len(top_keys) if isinstance(top_keys, list) else 1,
        "total_tensor_keys": len(keys),
        "module_prefix_count": len(module_keys),
        "orig_mod_prefix_count": len(orig_mod_keys),
        "plain_keys_count": len(plain_keys),
        "total_parameter_count": total_params,
        "total_tensor_bytes": total_bytes,
        "total_tensor_mb": round(total_bytes / (1024 * 1024), 2),
        "dtypes": dtypes,
        "first_5_keys": keys[:5],
        "last_5_keys": keys[-5:],
        "chakranet_load_test": chakranet_test
    }

# 2. Inspect best.pt (YOLO)
yolo_path = os.path.join(workspace, "weights", "best.pt")
if os.path.exists(yolo_path):
    print("Loading best.pt on CPU...")
    try:
        yolo_ckpt = torch.load(yolo_path, map_location="cpu")
        if isinstance(yolo_ckpt, dict):
            yolo_top_keys = list(yolo_ckpt.keys())
            model_info = {}
            if "model" in yolo_ckpt:
                ym = yolo_ckpt["model"]
                model_info["type"] = str(type(ym))
                if hasattr(ym, "names"):
                    model_info["names"] = ym.names
                if hasattr(ym, "nc"):
                    model_info["nc"] = ym.nc
                if hasattr(ym, "parameters"):
                    model_info["param_count"] = sum(p.numel() for p in ym.parameters())
            results["best.pt"] = {
                "file_size_bytes": os.path.getsize(yolo_path),
                "is_dict": True,
                "top_keys": yolo_top_keys,
                "epoch": yolo_ckpt.get("epoch"),
                "best_fitness": str(yolo_ckpt.get("best_fitness")),
                "date": yolo_ckpt.get("date"),
                "model_info": model_info
            }
        else:
            results["best.pt"] = {
                "type": str(type(yolo_ckpt))
            }
    except Exception as ye:
        results["best.pt"] = {"error": str(ye)}

import json
out_file = os.path.join(workspace, ".agents", "explorer_m1_3_g7", "checkpoint_details.json")
with open(out_file, "w") as f:
    json.dump(results, f, indent=2)

print("Checkpoint inspection complete. Saved to checkpoint_details.json")
