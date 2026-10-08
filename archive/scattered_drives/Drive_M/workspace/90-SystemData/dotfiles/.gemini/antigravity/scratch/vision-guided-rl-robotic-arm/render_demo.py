"""
Render Demonstration Videos & Visual Trajectories for Robotic Arm
"""

import os
import argparse
import yaml
import torch
import imageio
import numpy as np
from src.robotic_arm_env import VisionGuidedPandaArmEnv
from src.multimodal_policy import MultiModalActorCritic


def record_manipulator_demo(
    checkpoint_path: str,
    config_path: str = "configs/arm_reach_config.yaml",
    output_path: str = "./logs/arm_reach_demo.mp4",
    num_episodes: int = 3,
    fps: int = 30,
):
    """Renders high-definition demonstration rollouts and saves to MP4/GIF."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    device = torch.device("cpu")
    v_cfg = config.get("vision_backbone", {})
    model = MultiModalActorCritic(
        proprio_dim=17,
        action_dim=7,
        latent_dim=v_cfg.get("latent_dim", 128),
        pretrained_vision=v_cfg.get("pretrained", True),
        freeze_backbone=v_cfg.get("freeze_backbone", True),
    ).to(device)

    if os.path.exists(checkpoint_path):
        print(f"[*] Loading model weights from: {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        print("[!] Warning: Checkpoint not found, rendering rollout with initialized policy.")

    model.eval()
    env = VisionGuidedPandaArmEnv(config=config, render_mode=None)
    frames = []

    print(f"[*] Recording {num_episodes} demonstration episodes...")
    for ep in range(num_episodes):
        obs, info = env.reset(seed=100 + ep)
        done = False
        truncated = False

        while not (done or truncated):
            frame = env.render()
            if frame is not None:
                frames.append(frame)

            rgb_t = torch.tensor(obs["rgb"], dtype=torch.float32).unsqueeze(0)
            proprio_t = torch.tensor(obs["proprioception"], dtype=torch.float32).unsqueeze(0)

            with torch.no_grad():
                features = model.extract_features(rgb_t, proprio_t)
                action = model.actor_mean(features).squeeze(0).numpy()

            obs, reward, done, truncated, _ = env.step(action)

    env.close()

    if output_path.endswith(".gif"):
        imageio.mimsave(output_path, frames, fps=fps, loop=0)
    else:
        try:
            imageio.mimsave(output_path, frames, fps=fps, macro_block_size=1)
        except Exception:
            gif_path = output_path.replace(".mp4", ".gif")
            imageio.mimsave(gif_path, frames, fps=fps)
            output_path = gif_path

    print(f"[[OK]] Demonstration video recorded successfully -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record Robotic Arm Video Demo")
    parser.add_argument("--checkpoint", type=str, default="./models/checkpoints/vision_arm_ppo_final.pt")
    parser.add_argument("--config", type=str, default="configs/arm_reach_config.yaml")
    parser.add_argument("--output", type=str, default="./logs/arm_reach_demo.mp4")
    parser.add_argument("--episodes", type=int, default=3)
    args = parser.parse_args()

    record_manipulator_demo(
        checkpoint_path=args.checkpoint,
        config_path=args.config,
        output_path=args.output,
        num_episodes=args.episodes,
    )
