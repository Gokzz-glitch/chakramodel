import torch
import torch.nn as nn
import torch.nn.functional as F
import timm


class ChakraLiveStudent(nn.Module):
    """Compact segmentation student for live video deployment."""

    def __init__(
        self, backbone_name="mobilenetv3_small_100", num_classes=1, pretrained=True
    ):
        super().__init__()
        self.encoder = timm.create_model(
            backbone_name,
            pretrained=pretrained,
            features_only=True,
            out_indices=(1, 2, 3, 4),
        )
        channels = self.encoder.feature_info.channels()
        decoder_channels = 128
        self.projections = nn.ModuleList(
            [nn.Conv2d(channel, decoder_channels, 1) for channel in channels]
        )
        self.fuse = nn.Sequential(
            nn.Conv2d(decoder_channels, decoder_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(decoder_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(decoder_channels, decoder_channels // 2, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(decoder_channels // 2, num_classes, 1),
        )

    def forward(self, x):
        height, width = x.shape[-2:]
        features = self.encoder(x)
        decoded = self.projections[-1](features[-1])
        for feature, projection in zip(reversed(features[:-1]), reversed(self.projections[:-1])):
            decoded = F.interpolate(
                decoded, size=feature.shape[-2:], mode="bilinear", align_corners=False
            )
            decoded = decoded + projection(feature)
        logits = self.fuse(decoded)
        return F.interpolate(logits, size=(height, width), mode="bilinear", align_corners=False)
