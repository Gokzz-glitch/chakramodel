"""
Standalone Agent Evaluation & Visualizer CLI
============================================
Evaluates a saved checkpoint, outputs statistical tables, and records demo video.
"""

import os
import argparse
import yaml
import torch
from stable_baselines3 import PPO
from src.evaluate import evaluate_policy_statistical
from src.visualize import plot_reward_distribution, record_policy_video
from src.custom_ppo import ActorCritic
import gymnasium as gym


def main():
    parser = argparse.ArgumentParser(description="Evaluate LunarLander PPO Policy Checkpoint")
    parser.add_argument("--model-path", type=str, required=True, help="Path to .zip (SB3) or .pt (PyTorch) model file")
    parser.add_argument("--episodes", type=int, default=100, help="Number of evaluation episodes")
    parser.add_argument("--continuous", action="store_true", help="Continuous action space")
    parser.add_argument("--output-video", type=str, default="./logs/eval_demo.mp4", help="Video output destination")
    parser.add_argument("--output-plot", type=str, default="./logs/eval_distribution.png", help="Plot output destination")
    args = parser.parse_args()

    env_id = "LunarLander-v2"
    is_custom = args.model_path.endswith(".pt")

    if is_custom:
        print(f"[*] Loading Custom PyTorch checkpoint from: {args.model_path}")
        temp_env = gym.make(env_id, continuous=args.continuous)
        checkpoint = torch.load(args.model_path, map_location="cpu")
        model = ActorCritic(
            temp_env.observation_space,
            temp_env.action_space,
            hidden_dim=checkpoint.get("config", {}).get("hidden_dim", 128),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        temp_env.close()
    else:
        print(f"[*] Loading Stable-Baselines3 model from: {args.model_path}")
        model = PPO.load(args.model_path)

    # 1. Run statistical evaluation
    results = evaluate_policy_statistical(
        model=model,
        env_id=env_id,
        continuous=args.continuous,
        n_episodes=args.episodes,
        is_custom_pytorch=is_custom,
    )

    # 2. Plot distribution
    plot_reward_distribution(
        rewards=results["rewards_raw"],
        save_path=args.output_plot,
        title=f"LunarLander ({'Continuous' if args.continuous else 'Discrete'}) Evaluation (N={args.episodes})",
    )

    # 3. Record video
    record_policy_video(
        model=model,
        env_id=env_id,
        continuous=args.continuous,
        output_path=args.output_video,
        is_custom_pytorch=is_custom,
    )


if __name__ == "__main__":
    main()
