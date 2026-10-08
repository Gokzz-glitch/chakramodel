"""
Standalone Benchmark Evaluation CLI for Vision-Guided Robotic Arm
"""

import os
import argparse
import yaml
import torch
from src.multimodal_policy import MultiModalActorCritic
from src.evaluate_policy import benchmark_robotic_arm_policy


def main():
    parser = argparse.ArgumentParser(description="Evaluate Trained Vision-Guided Robotic Arm Model")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to .pt checkpoint file")
    parser.add_argument("--config", type=str, default="configs/arm_reach_config.yaml", help="Path to config YAML")
    parser.add_argument("--episodes", type=int, default=50, help="Number of benchmark trials")
    parser.add_argument("--device", type=str, default="cpu", help="Device (cpu or cuda)")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    device = torch.device(args.device)
    print(f"[*] Loading checkpoint from: {args.checkpoint}")
    checkpoint = torch.load(args.checkpoint, map_location=device)

    v_cfg = config.get("vision_backbone", {})
    model = MultiModalActorCritic(
        proprio_dim=17,
        action_dim=7,
        latent_dim=v_cfg.get("latent_dim", 128),
        pretrained_vision=v_cfg.get("pretrained", True),
        freeze_backbone=v_cfg.get("freeze_backbone", True),
    ).to(device)

    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    benchmark_robotic_arm_policy(
        model=model,
        config=config,
        n_episodes=args.episodes,
        device=args.device,
    )


if __name__ == "__main__":
    main()
