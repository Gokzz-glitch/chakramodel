import torch
import torch.nn as nn
import torch.nn.functional as F
import timm


class _FeatureFusionBlock(nn.Module):
    """DPT-style residual refinement and upsampling block."""

    def __init__(self, features):
        super().__init__()
        self.refine = nn.Sequential(
            nn.Conv2d(features, features, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(features),
            nn.ReLU(inplace=True),
            nn.Conv2d(features, features, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(features),
        )
        self.activation = nn.ReLU(inplace=True)

    def forward(self, x, skip=None):
        if skip is not None:
            x = x + skip
        return F.interpolate(
            self.activation(x + self.refine(x)),
            scale_factor=2,
            mode="bilinear",
            align_corners=False,
        )


class ChakraTransformerSegmenter(nn.Module):
    """
    DPT-style ViT segmenter for polyp masks.

    Compared with the original single-feature decoder, this reassembles four
    transformer depths at 1/4, 1/2, 1, and 2 times the patch-grid resolution.
    The design follows the useful EndoViT segmentation idea while retaining a
    timm ImageNet backbone and ChakraModel's binary-mask output.
    """

    def __init__(
        self,
        backbone_name="vit_large_patch16_384",
        pretrained=True,
        num_classes=1,
        decoder_features=256,
    ):
        super().__init__()
        self.backbone = timm.create_model(
            backbone_name, pretrained=pretrained, num_classes=0
        )
        self.embed_dim = self.backbone.embed_dim
        self.patch_size = self._get_patch_size()

        if len(self.backbone.blocks) < 4:
            raise ValueError("The ViT backbone must contain at least four blocks")

        block_count = len(self.backbone.blocks)
        self.feature_layers = [
            block_count // 4 - 1,
            block_count // 2 - 1,
            (3 * block_count) // 4 - 1,
            block_count - 1,
        ]
        self._features = {}
        for index, layer_index in enumerate(self.feature_layers):
            self.backbone.blocks[layer_index].register_forward_hook(
                self._capture_feature(index)
            )

        # Reassemble the four token maps into DPT's multi-scale feature pyramid.
        self.reassemble = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Conv2d(self.embed_dim, decoder_features, kernel_size=1),
                    nn.ConvTranspose2d(
                        decoder_features, decoder_features, kernel_size=4, stride=4
                    ),
                ),
                nn.Sequential(
                    nn.Conv2d(self.embed_dim, decoder_features, kernel_size=1),
                    nn.ConvTranspose2d(
                        decoder_features, decoder_features, kernel_size=2, stride=2
                    ),
                ),
                nn.Conv2d(self.embed_dim, decoder_features, kernel_size=1),
                nn.Sequential(
                    nn.Conv2d(self.embed_dim, decoder_features, kernel_size=1),
                    nn.Conv2d(
                        decoder_features,
                        decoder_features,
                        kernel_size=3,
                        stride=2,
                        padding=1,
                    ),
                ),
            ]
        )

        self.refine4 = _FeatureFusionBlock(decoder_features)
        self.refine3 = _FeatureFusionBlock(decoder_features)
        self.refine2 = _FeatureFusionBlock(decoder_features)
        self.refine1 = _FeatureFusionBlock(decoder_features)
        self.decode_head = nn.Sequential(
            nn.Conv2d(decoder_features, decoder_features // 2, 3, padding=1),
            nn.BatchNorm2d(decoder_features // 2),
            nn.ReLU(inplace=True),
            nn.Dropout2d(0.1),
            nn.Conv2d(decoder_features // 2, num_classes, 1),
        )

    def _capture_feature(self, index):
        def hook(_module, _inputs, output):
            self._features[index] = output

        return hook

    def _get_patch_size(self):
        patch_size = getattr(self.backbone.patch_embed, "patch_size", 16)
        return patch_size[0] if isinstance(patch_size, tuple) else patch_size

    def _tokens_to_map(self, tokens, grid_h, grid_w):
        if tokens.ndim != 3:
            raise RuntimeError(
                f"Expected ViT block tokens with shape [B, N, C], got {tuple(tokens.shape)}"
            )
        expected_tokens = grid_h * grid_w
        if tokens.shape[1] == expected_tokens + 1:
            tokens = tokens[:, 1:]
        if tokens.shape[1] != expected_tokens:
            raise RuntimeError(
                "ViT token count does not match the input patch grid; "
                f"expected {expected_tokens} or {expected_tokens + 1}, got {tokens.shape[1]}"
            )
        return tokens.transpose(1, 2).reshape(
            tokens.shape[0], self.embed_dim, grid_h, grid_w
        )

    def forward(self, x):
        _, _, height, width = x.shape
        if height % self.patch_size or width % self.patch_size:
            raise ValueError(
                f"Input size {(height, width)} must be divisible by patch size "
                f"{self.patch_size}"
            )

        self._features.clear()
        self.backbone.forward_features(x)
        missing = [i for i in range(4) if i not in self._features]
        if missing:
            raise RuntimeError(f"ViT feature hooks did not produce layers: {missing}")

        grid_h, grid_w = height // self.patch_size, width // self.patch_size
        layers = [
            self._tokens_to_map(self._features[i], grid_h, grid_w)
            for i in range(4)
        ]
        layer1, layer2, layer3, layer4 = [
            projection(feature)
            for projection, feature in zip(self.reassemble, layers)
        ]

        path4 = self.refine4(layer4)
        path3 = self.refine3(path4, layer3)
        path2 = self.refine2(path3, layer2)
        path1 = self.refine1(path2, layer1)
        logits = self.decode_head(path1)
        return F.interpolate(
            logits, size=(height, width), mode="bilinear", align_corners=False
        )


if __name__ == "__main__":
    model = ChakraTransformerSegmenter(pretrained=False)
    dummy_input = torch.randn(2, 3, 384, 384)
    output = model(dummy_input)
    print(f"Model output shape: {output.shape} (Expected: [2, 1, 384, 384])")
