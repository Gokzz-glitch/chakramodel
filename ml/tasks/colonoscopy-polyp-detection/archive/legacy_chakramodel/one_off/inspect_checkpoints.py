import torch
from pathlib import Path

# The two main checkpoint files
ckpts = [
    Path(r'm:\chakramodel\weights\chakra_transformer_best.pth'),
    Path(r'm:\chakramodel\weights\chakra_transformer_vit_large_best (1).pth'),
]

for ckpt_path in ckpts:
    print(f"\n{'='*80}")
    print(f"CHECKPOINT: {ckpt_path.name}  ({ckpt_path.stat().st_size / 1e6:.1f} MB)")
    print(f"{'='*80}")
    
    sd = torch.load(str(ckpt_path), map_location='cpu', weights_only=True)
    
    # Check if wrapped
    if isinstance(sd, dict) and 'model_state_dict' in sd:
        print("  Wrapped in 'model_state_dict' key")
        sd = sd['model_state_dict']
    elif isinstance(sd, dict) and 'state_dict' in sd:
        print("  Wrapped in 'state_dict' key")
        sd = sd['state_dict']
    else:
        print("  Raw state_dict (not wrapped)")
    
    # Count and categorize keys
    backbone_keys = [k for k in sd.keys() if k.startswith('backbone')]
    decode_head_keys = [k for k in sd.keys() if k.startswith('decode_head')]
    stage_keys = [k for k in sd.keys() if k.startswith('stage')]
    final_conv_keys = [k for k in sd.keys() if k.startswith('final_conv')]
    dropout_keys = [k for k in sd.keys() if k.startswith('dropout')]
    other_keys = [k for k in sd.keys() if not any(k.startswith(p) for p in ['backbone', 'decode_head', 'stage', 'final_conv', 'dropout'])]
    
    total_params = sum(v.numel() for v in sd.values())
    
    print(f"\n  Total keys: {len(sd)}")
    print(f"  Total parameters: {total_params:,} ({total_params/1e6:.2f}M)")
    print(f"\n  Backbone keys: {len(backbone_keys)}")
    print(f"  decode_head keys: {len(decode_head_keys)}")
    print(f"  stage* keys: {len(stage_keys)}")
    print(f"  final_conv keys: {len(final_conv_keys)}")
    print(f"  dropout keys: {len(dropout_keys)}")
    print(f"  other keys: {len(other_keys)}")
    
    # Print non-backbone keys with shapes (decoder keys are what matters)
    print(f"\n  --- DECODER KEYS (non-backbone) ---")
    for k, v in sorted(sd.items()):
        if not k.startswith('backbone'):
            print(f"  {k}: {tuple(v.shape)}")
    
    # Print first 5 backbone keys as sanity check
    print(f"\n  --- FIRST 5 BACKBONE KEYS ---")
    for k in sorted(backbone_keys)[:5]:
        print(f"  {k}: {tuple(sd[k].shape)}")
