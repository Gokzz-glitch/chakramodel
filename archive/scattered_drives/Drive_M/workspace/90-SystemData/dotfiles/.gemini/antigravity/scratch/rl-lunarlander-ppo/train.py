"""
Main Training Entrypoint for LunarLander PPO
=============================================
Supports both production Stable-Baselines3 engine and pure PyTorch implementation.
"""

import os
import argparse
import yaml
import torch
import gymnasium as gym
from src.sb3_pipeline import train_sb3_ppo
from src.custom_ppo import CustomPPOAgent
from src.env_wrappers import make_env
from src.evaluate import evaluate_policy_statistical
from src.visualize import plot_reward_distribution, record_policy_video


def load_config(config_path: str) -> dict:
    """Load YAML configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def train_custom_pytorch(config: dict):
    """Executes training loop with custom PyTorch PPO agent."""
    env_cfg = config.get("environment", {})
    train_cfg = config.get("training", {})
    ppo_cfg = config.get("ppo", {})

    env_id = env_cfg.get("env_id", "LunarLander-v2")
    continuous = env_cfg.get("continuous", False)
    num_envs = env_cfg.get("num_envs", 8)
    seed = env_cfg.get("seed", 42)
    total_timesteps = train_cfg.get("total_timesteps", 500000)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Custom PyTorch PPO Agent on device: {device}")

    # Vectorized environments
    envs = gym.vector.SyncVectorEnv(
        [
            make_env(
                env_id=env_id,
                continuous=continuous,
                seed=seed,
                idx=i,
                shape_reward=False,
                normalize_obs=env_cfg.get("normalize_obs", True),
            )
            for i in range(num_envs)
        ]
    )

    agent = CustomPPOAgent(envs, ppo_cfg, device=device)

    # Initialize rollout state
    next_obs, _ = envs.reset(seed=seed)
    next_obs = torch.tensor(next_obs, dtype=torch.float32, device=device)
    next_done = torch.zeros(num_envs, dtype=torch.float32, device=device)

    num_iterations = total_timesteps // (num_envs * ppo_cfg.get("n_steps", 1024))
    print(f"[*] Commencing Custom PPO Training ({num_iterations} iterations, {total_timesteps} total steps)...")

    checkpoint_dir = train_cfg.get("checkpoint_dir", "./models/checkpoints_custom")
    os.makedirs(checkpoint_dir, exist_ok=True)

    for iteration in range(1, num_iterations + 1):
        global_step = iteration * (num_envs * ppo_cfg.get("n_steps", 1024))
        next_obs, next_done, metrics = agent.train_step(global_step, next_obs, next_done)

        if iteration % 10 == 0 or iteration == num_iterations:
            print(
                f"[Iter {iteration:04d}/{num_iterations:04d} | Step {global_step:07d}] "
                f"Policy Loss: {metrics['policy_loss']:.4f} | Value Loss: {metrics['value_loss']:.4f} | "
                f"Entropy: {metrics['entropy']:.4f} | Approx KL: {metrics['approx_kl']:.5f}"
            )

        if iteration % 50 == 0 or iteration == num_iterations:
            ckpt_path = os.path.join(checkpoint_dir, f"custom_ppo_step_{global_step}.pt")
            agent.save(ckpt_path)

    final_path = os.path.join(checkpoint_dir, "custom_ppo_final.pt")
    agent.save(final_path)
    print(f"[[OK]] Custom PyTorch PPO Training finished! Model saved -> {final_path}")
    envs.close()
    return agent


def main():
    parser = argparse.ArgumentParser(description="Train PPO Agent on LunarLander-v2")
    parser.add_argument("--mode", type=str, choices=["sb3", "custom"], default="sb3", help="Training engine")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML configuration file")
    parser.add_argument("--continuous", action="store_true", help="Train on continuous action space")
    parser.add_argument("--timesteps", type=int, default=None, help="Override total timesteps")
    parser.add_argument("--evaluate", action="store_true", default=True, help="Run evaluation after training")
    args = parser.parse_args()

    # Determine default config if none supplied
    if args.config is None:
        args.config = (
            "configs/ppo_continuous.yaml" if args.continuous else "configs/ppo_default.yaml"
        )

    print(f"[*] Loading configuration from: {args.config}")
    config = load_config(args.config)

    if args.continuous:
        config["environment"]["continuous"] = True
    if args.timesteps:
        config["training"]["total_timesteps"] = args.timesteps

    # Launch Training
    if args.mode == "sb3":
        model = train_sb3_ppo(config)
        is_custom = False
    else:
        model = train_custom_pytorch(config)
        is_custom = True

    # Post-training Evaluation & Visualizations
    if args.evaluate:
        print("\n" + "=" * 60)
        print("          EXECUTING POST-TRAINING BENCHMARK          ")
        print("=" * 60)
        continuous_env = config["environment"]["continuous"]
        eval_results = evaluate_policy_statistical(
            model=model,
            env_id="LunarLander-v2",
            continuous=continuous_env,
            n_episodes=100,
            is_custom_pytorch=is_custom,
        )

        plot_reward_distribution(
            rewards=eval_results["rewards_raw"],
            save_path="./logs/evaluation_returns_distribution.png",
            title=f"LunarLander-v2 ({'Continuous' if continuous_env else 'Discrete'}) 100-Seed Returns",
        )

        record_policy_video(
            model=model,
            env_id="LunarLander-v2",
            continuous=continuous_env,
            output_path="./logs/lunarlander_agent_landing.mp4",
            is_custom_pytorch=is_custom,
        )


if __name__ == "__main__":
    main()
