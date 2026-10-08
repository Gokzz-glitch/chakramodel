"""
Vision-Guided 7-DOF Robotic Arm PPO Training Orchestrator
=========================================================
Trains an end-to-end multi-modal policy mapping raw RGB camera feeds + joint proprioception
into continuous 7-DOF joint velocity actions.
"""

import os
import argparse
import time
import yaml
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from src.robotic_arm_env import VisionGuidedPandaArmEnv
from src.multimodal_policy import MultiModalActorCritic
from src.evaluate_policy import benchmark_robotic_arm_policy


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def train_vision_arm(config: dict, device: torch.device):
    ppo_cfg = config.get("ppo", {})
    train_cfg = config.get("training", {})
    v_cfg = config.get("vision_backbone", {})
    r_cfg = config.get("robot", {})

    total_timesteps = train_cfg.get("total_timesteps", 1000000)
    n_steps = ppo_cfg.get("n_steps", 1024)
    batch_size = ppo_cfg.get("batch_size", 64)
    n_epochs = ppo_cfg.get("n_epochs", 10)
    lr = ppo_cfg.get("learning_rate", 3e-4)
    gamma = ppo_cfg.get("gamma", 0.99)
    gae_lambda = ppo_cfg.get("gae_lambda", 0.95)
    clip_range = ppo_cfg.get("clip_range", 0.2)
    ent_coef = ppo_cfg.get("ent_coef", 0.005)
    vf_coef = ppo_cfg.get("vf_coef", 0.5)
    max_grad_norm = ppo_cfg.get("max_grad_norm", 0.5)

    checkpoint_dir = train_cfg.get("checkpoint_dir", "./models/checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)

    print(f"[*] Initializing Multi-Modal Panda Arm Environment on device: {device}")
    env = VisionGuidedPandaArmEnv(config=config, render_mode=None)

    # Initialize Multi-Modal Actor-Critic Network
    model = MultiModalActorCritic(
        proprio_dim=17,
        action_dim=7,
        latent_dim=v_cfg.get("latent_dim", 128),
        pretrained_vision=v_cfg.get("pretrained", True),
        freeze_backbone=v_cfg.get("freeze_backbone", True),
    ).to(device)

    optimizer = optim.Adam(model.parameters(), lr=lr, eps=1e-5)

    # Rollout buffer allocation
    obs_rgb_buf = torch.zeros((n_steps, 128, 128, 3), dtype=torch.float32, device=device)
    obs_prop_buf = torch.zeros((n_steps, 17), dtype=torch.float32, device=device)
    actions_buf = torch.zeros((n_steps, 7), dtype=torch.float32, device=device)
    logprobs_buf = torch.zeros(n_steps, dtype=torch.float32, device=device)
    rewards_buf = torch.zeros(n_steps, dtype=torch.float32, device=device)
    dones_buf = torch.zeros(n_steps, dtype=torch.float32, device=device)
    values_buf = torch.zeros(n_steps, dtype=torch.float32, device=device)

    # Reset environment
    obs, _ = env.reset(seed=42)
    curr_rgb = torch.tensor(obs["rgb"], dtype=torch.float32, device=device)
    curr_proprio = torch.tensor(obs["proprioception"], dtype=torch.float32, device=device)
    curr_done = 0.0

    num_iterations = total_timesteps // n_steps
    print(f"[*] Commencing Vision-Guided RL Training for {num_iterations} iterations ({total_timesteps} total steps)...")

    for iteration in range(1, num_iterations + 1):
        # 1. Rollout Collection Phase
        for step in range(n_steps):
            obs_rgb_buf[step] = curr_rgb
            obs_prop_buf[step] = curr_proprio
            dones_buf[step] = curr_done

            with torch.no_grad():
                action, logprob, _, value = model.get_action_and_value(
                    curr_rgb.unsqueeze(0), curr_proprio.unsqueeze(0)
                )
                values_buf[step] = value.squeeze()

            actions_buf[step] = action.squeeze(0)
            logprobs_buf[step] = logprob.squeeze()

            # Execute action in PyBullet
            action_np = action.squeeze(0).cpu().numpy()
            obs, reward, terminated, truncated, _ = env.step(action_np)
            done = terminated or truncated

            rewards_buf[step] = float(reward)
            curr_done = 1.0 if done else 0.0

            if done:
                obs, _ = env.reset()

            curr_rgb = torch.tensor(obs["rgb"], dtype=torch.float32, device=device)
            curr_proprio = torch.tensor(obs["proprioception"], dtype=torch.float32, device=device)

        # 2. GAE Advantage Calculation
        with torch.no_grad():
            next_value = model.get_value(curr_rgb.unsqueeze(0), curr_proprio.unsqueeze(0)).squeeze()

        advantages = torch.zeros(n_steps, dtype=torch.float32, device=device)
        lastgaelam = 0.0
        for t in reversed(range(n_steps)):
            if t == n_steps - 1:
                nextnonterminal = 1.0 - curr_done
                nextvalues = next_value
            else:
                nextnonterminal = 1.0 - dones_buf[t + 1]
                nextvalues = values_buf[t + 1]

            delta = rewards_buf[t] + gamma * nextvalues * nextnonterminal - values_buf[t]
            advantages[t] = lastgaelam = delta + gamma * gae_lambda * nextnonterminal * lastgaelam

        returns = advantages + values_buf
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # 3. Optimization Phase
        b_inds = np.arange(n_steps)
        for epoch in range(n_epochs):
            np.random.shuffle(b_inds)
            for start in range(0, n_steps, batch_size):
                end = start + batch_size
                mb_inds = b_inds[start:end]

                _, newlogprob, entropy, newvalue = model.get_action_and_value(
                    obs_rgb_buf[mb_inds], obs_prop_buf[mb_inds], actions_buf[mb_inds]
                )

                logratio = newlogprob - logprobs_buf[mb_inds]
                ratio = logratio.exp()

                mb_advantages = advantages[mb_inds]

                # Policy Loss (Clipped Objective)
                pg_loss1 = -mb_advantages * ratio
                pg_loss2 = -mb_advantages * torch.clamp(ratio, 1 - clip_range, 1 + clip_range)
                pg_loss = torch.max(pg_loss1, pg_loss2).mean()

                # Value Loss
                v_loss = 0.5 * ((newvalue.squeeze() - returns[mb_inds]) ** 2).mean()

                # Total Loss
                loss = pg_loss - ent_coef * entropy.mean() + vf_coef * v_loss

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
                optimizer.step()

        if iteration % 5 == 0 or iteration == num_iterations:
            global_step = iteration * n_steps
            print(
                f"[Iteration {iteration:04d}/{num_iterations:04d} | Step {global_step:07d}] "
                f"Policy Loss: {pg_loss.item():.4f} | Value Loss: {v_loss.item():.4f} | "
                f"Avg Reward: {rewards_buf.mean().item():.2f}"
            )

        if iteration % 20 == 0 or iteration == num_iterations:
            ckpt_file = os.path.join(checkpoint_dir, f"vision_arm_ppo_iter_{iteration}.pt")
            torch.save({"model_state_dict": model.state_dict(), "config": config}, ckpt_file)

    final_save_path = os.path.join(checkpoint_dir, "vision_arm_ppo_final.pt")
    torch.save({"model_state_dict": model.state_dict(), "config": config}, final_save_path)
    print(f"[[OK]] Model training finished successfully! Saved to: {final_save_path}")

    env.close()
    return model


def main():
    parser = argparse.ArgumentParser(description="Train Vision-Guided Robotic Arm with PPO")
    parser.add_argument("--config", type=str, default="configs/arm_reach_config.yaml", help="Path to config YAML")
    parser.add_argument("--timesteps", type=int, default=None, help="Override total timesteps")
    parser.add_argument("--device", type=str, default=None, help="Device (cuda or cpu)")
    parser.add_argument("--evaluate", action="store_true", default=True, help="Run benchmark evaluation after training")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.timesteps:
        config["training"]["total_timesteps"] = args.timesteps

    device_str = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_str)

    trained_model = train_vision_arm(config, device)

    if args.evaluate:
        print("\n" + "=" * 65)
        print("          LAUNCHING POST-TRAINING BENCHMARK SUITE          ")
        print("=" * 65)
        benchmark_robotic_arm_policy(
            model=trained_model,
            config=config,
            n_episodes=50,
            device=str(device),
        )


if __name__ == "__main__":
    main()
