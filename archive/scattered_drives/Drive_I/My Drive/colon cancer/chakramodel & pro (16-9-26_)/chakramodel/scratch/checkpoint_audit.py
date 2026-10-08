import torch
import os
import hashlib

def get_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def inspect_checkpoint(path, name):
    print(f"\n{'='*60}")
    print(f"Inspecting: {name}")
    print(f"Path: {path}")
    if not os.path.exists(path):
        print("FILE NOT FOUND")
        return None
    
    size_mb = os.path.getsize(path) / (1024*1024)
    print(f"Size: {size_mb:.1f} MB")
    
    try:
        if path.endswith('.pt') or path.endswith('.pth') or path.endswith('.bak'):
            ckpt = torch.load(path, map_location='cpu', weights_only=False)
        else:
            return
            
        if isinstance(ckpt, dict):
            if 'state_dict' in ckpt:
                sd = ckpt['state_dict']
            elif 'model' in ckpt:
                sd = ckpt['model']
            else:
                sd = ckpt
        else:
            sd = ckpt
            
        if isinstance(sd, dict):
            keys = list(sd.keys())
            n_keys = len(keys)
            has_module_prefix = any(str(k).startswith('module.') for k in keys)
            n_params = sum(p.numel() for p in sd.values() if hasattr(p, 'numel'))
            
            print(f"Total keys: {n_keys}")
            print(f"Has 'module.' prefix: {has_module_prefix}")
            print(f"Total parameters: {n_params:,}")
            print(f"First 5 keys: {keys[:5]}")
            print(f"Last 5 keys: {keys[-5:]}")
            return keys
        else:
            print("Not a standard state dict.")
            print(type(sd))
            return None
    except Exception as e:
        print(f"ERROR loading: {e}")
        return None

base_dir = r"M:\chakramodel"
weights_dir = os.path.join(base_dir, "weights")

checkpoints = [
    (os.path.join(weights_dir, "chakra_transformer_best.pth"), "chakra_transformer_best.pth"),
    (os.path.join(weights_dir, "chakra_transformer_best.pth.bak"), "chakra_transformer_best.pth.bak"),
    (os.path.join(weights_dir, "combo1_best.pth"), "combo1_best.pth"),
    (os.path.join(weights_dir, "combo2_best.pth"), "combo2_best.pth"),
    (os.path.join(weights_dir, "pranet_kvasir_best.pth"), "pranet_kvasir_best.pth"),
    (os.path.join(base_dir, "src", "yolov8x.pt"), "yolov8x.pt")
]

hashes = {}
for path, name in checkpoints:
    if os.path.exists(path):
        hashes[name] = get_hash(path)
    inspect_checkpoint(path, name)

if 'combo1_best.pth' in hashes and 'combo2_best.pth' in hashes:
    if hashes['combo1_best.pth'] == hashes['combo2_best.pth']:
        print("\ncombo1_best.pth and combo2_best.pth are EXACT DUPLICATES (hash match)")
    else:
        print("\ncombo1_best.pth and combo2_best.pth are DIFFERENT FILES")
