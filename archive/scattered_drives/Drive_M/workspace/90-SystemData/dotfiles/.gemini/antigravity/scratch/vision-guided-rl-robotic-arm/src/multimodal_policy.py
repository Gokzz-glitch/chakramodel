"""
Multi-Modal Actor-Critic Architecture Fusing Visual & Proprioceptive Embeddings
"""

import torch
import torch.nn as nn
from torch.distributions.normal import Normal
from typing import Tuple, Optional, Dict
import gymnasium as gym

from .vision_backbone import VisionBackbone


class MultiModalActorCritic(nn.Module):
    """
    Dual-stream Multi-Modal Actor-Critic Network.
    
    Streams:
    1. Vision Stream: RGB frames -> Frozen ResNet-18 + Projection Head -> Latent Vector (d=128)
    2. Proprioception Stream: 7 Joint Positions + 7 Velocities + 3 EE Coords -> MLP -> Feature Vector (d=64)
    3. Fusion Layer: Concatenated (128 + 64) -> Shared Representation (d=256)
    4. Policy Head: Continuous 7-DOF Joint Action Mean + Learnable Log-Std
    5. Critic Head: Scalar State Value V(s)
    """

    def __init__(
        self,
        proprio_dim: int = 17,
        action_dim: int = 7,
        latent_dim: int = 128,
        hidden_dim: int = 256,
        pretrained_vision: bool = True,
        freeze_backbone: bool = True,
    ):
        super().__init__()
        self.action_dim = action_dim

        # 1. Vision Feature Extractor
        self.vision_backbone = VisionBackbone(
            latent_dim=latent_dim,
            pretrained=pretrained_vision,
            freeze_backbone=freeze_backbone,
        )

        # 2. Proprioception MLP Encoder
        self.proprio_encoder = nn.Sequential(
            nn.Linear(proprio_dim, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
        )

        # 3. Fusion Backbone
        fusion_dim = latent_dim + 64
        self.fusion_layer = nn.Sequential(
            nn.Linear(fusion_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )

        # 4. Policy (Actor) Head
        self.actor_mean = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, action_dim),
            nn.Tanh(),  # Normalized actions in [-1.0, 1.0]
        )
        self.actor_logstd = nn.Parameter(torch.full((1, action_dim), -0.5))

        # 5. Critic (Value) Head
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

    def extract_features(self, rgb: torch.Tensor, proprio: torch.Tensor) -> torch.Tensor:
        """Fuses vision and proprioception into joint representation."""
        v_feat = self.vision_backbone(rgb)
        p_feat = self.proprio_encoder(proprio)
        fused = torch.cat([v_feat, p_feat], dim=-1)
        return self.fusion_layer(fused)

    def get_value(self, rgb: torch.Tensor, proprio: torch.Tensor) -> torch.Tensor:
        """Estimates state value V(s)."""
        feat = self.extract_features(rgb, proprio)
        return self.critic(feat)

    def get_action_and_value(
        self,
        rgb: torch.Tensor,
        proprio: torch.Tensor,
        action: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Samples action and evaluates log-prob, entropy, and value."""
        features = self.extract_features(rgb, proprio)
        action_mean = self.actor_mean(features)
        action_logstd = self.actor_logstd.expand_as(action_mean)
        action_std = torch.exp(action_logstd)

        dist = Normal(action_mean, action_std)
        if action is None:
            action = dist.sample()

        log_prob = dist.log_prob(action).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)
        value = self.critic(features)

        return action, log_prob, entropy, value
