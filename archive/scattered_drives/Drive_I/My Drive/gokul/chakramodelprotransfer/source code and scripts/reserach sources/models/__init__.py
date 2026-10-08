from .unet import UNet
import torch

def build_model(config: dict) -> torch.nn.Module:
    """
    Build a segmentation model from config.
    
    Args:
        config: Model config dict with keys like 'architecture', 'backbone',
                'pretrained', 'pretrained_source', etc.
    
    Returns:
        Segmentation model (nn.Module)
    """
    arch = config.get('architecture', 'unet')
    if arch == 'unet':
        return UNet(config=config)
    else:
        raise ValueError(f'Unknown architecture: {arch}')

