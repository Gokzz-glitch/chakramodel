from .unet import UNet
import torch

def build_model(config: dict) -> torch.nn.Module:
    arch = config.get('architecture', 'unet')
    if arch == 'unet':
        return UNet(
            backbone=config.get('backbone', 'resnet50'),
            pretrained=config.get('pretrained', True),
        )
    else:
        raise ValueError(f'Unknown architecture: {arch}')
