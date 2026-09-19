"""Lightweight CNN-Transformer U-Net with cross-attention skip fusion.

The model is intentionally small enough for a cloud T4/P100 and can be
evaluated on a laptop GPU.  ``timm`` supplies a hierarchical Swin encoder;
the decoder selectively reads each encoder skip through cross-attention rather
than concatenating the complete feature map.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
import timm


class CrossAttentionSkip(nn.Module):
    def __init__(self, query_channels: int, skip_channels: int, out_channels: int,
                 heads: int = 4, max_key_side: int = 16) -> None:
        super().__init__()
        self.max_key_side = max_key_side
        self.query = nn.Conv2d(query_channels, out_channels, 1, bias=False)
        self.key = nn.Conv2d(skip_channels, out_channels, 1, bias=False)
        self.value = nn.Conv2d(skip_channels, out_channels, 1, bias=False)
        self.attn = nn.MultiheadAttention(out_channels, heads, batch_first=True)
        self.gate = nn.Sequential(
            nn.Conv2d(out_channels * 2, out_channels, 1),
            nn.Sigmoid(),
        )
        self.refine = nn.Sequential(
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.GELU(),
        )

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        q_map = self.query(x)
        pooled_skip = F.adaptive_avg_pool2d(
            skip, (min(self.max_key_side, skip.shape[-2]),
                   min(self.max_key_side, skip.shape[-1]))
        )
        q = q_map.flatten(2).transpose(1, 2)
        k = self.key(pooled_skip).flatten(2).transpose(1, 2)
        v = self.value(pooled_skip).flatten(2).transpose(1, 2)
        attended, _ = self.attn(q, k, v, need_weights=False)
        attended = attended.transpose(1, 2).reshape_as(q_map)
        gate = self.gate(torch.cat((q_map, attended), dim=1))
        return self.refine(q_map + gate * attended)


class ChakraXAttnUNet(nn.Module):
    """Swin-Tiny encoder with boundary-guided, cross-attention decoding."""

    def __init__(self, backbone_name: str = "swin_tiny_patch4_window7_224",
                 pretrained: bool = True, num_classes: int = 1,
                 image_size: int = 224) -> None:
        super().__init__()
        self.encoder = timm.create_model(
            backbone_name, pretrained=pretrained, features_only=True,
            out_indices=(0, 1, 2, 3), img_size=image_size,
        )
        channels = self.encoder.feature_info.channels()
        decoder_channels = [128, 96, 64, 32]
        self.blocks = nn.ModuleList()
        in_channels = channels[-1]
        for skip_channels, out_channels in zip(reversed(channels[:-1]), decoder_channels):
            self.blocks.append(CrossAttentionSkip(in_channels, skip_channels, out_channels))
            in_channels = out_channels
        self.final = nn.Sequential(
            nn.Conv2d(in_channels, 32, 3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.GELU(),
        )
        self.mask_head = nn.Conv2d(32, num_classes, 1)
        self.boundary_head = nn.Conv2d(32, 1, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        input_size = x.shape[-2:]
        features = self.encoder(x)
        # timm normally returns NCHW; support NHWC backbones as well.
        channels = self.encoder.feature_info.channels()
        def nchw(feature: torch.Tensor, expected_channels: int) -> torch.Tensor:
            return feature if feature.shape[1] == expected_channels else feature.permute(
                0, 3, 1, 2
            ).contiguous()

        y = nchw(features[-1], channels[-1])
        for block, skip, skip_channels in zip(
            self.blocks, reversed(features[:-1]), reversed(channels[:-1])
        ):
            y = block(y, nchw(skip, skip_channels))
        y = F.interpolate(self.final(y), size=input_size, mode="bilinear", align_corners=False)
        return {
            "mask": self.mask_head(y),
            "boundary": self.boundary_head(y),
        }


if __name__ == "__main__":
    model = ChakraXAttnUNet(pretrained=False)
    output = model(torch.randn(1, 3, 352, 352))
    print({name: tuple(value.shape) for name, value in output.items()})
