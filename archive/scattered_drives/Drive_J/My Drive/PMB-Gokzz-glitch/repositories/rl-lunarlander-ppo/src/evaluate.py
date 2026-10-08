"""
Statistical Evaluation Engine for LunarLander PPO Policy
"""

import numpy as np
import gymnasium as gym
from typing import Dict, Any, Union
import torch


def evaluate_policy_statistical(
    model: Any,
    env_id: str = "LunarLander-v2",
    continuous: bool = False,
    n_episodes: int = 100,
    seed: int = 1000,
    is_custom_pytorch: bool = False,
    device: str = "cpu",
) -> Dict[str, Union[float, int, list]]:
    """
    Evaluates a trained policy across N Monte Carlo episodes with unique stochastic seeds.
    
    Returns comprehensive metrics:
    - mean_reward, std_reward, median_reward, min_reward, max_reward
    - success_rate (reward >= 200)
    - crash_rate (reward <= -100)
    - mean_episode_length
    """
    env = gym.make(env_id, continuous=continuous)
    episode_rewards = []
    episode_lengths = []
    successes = 0
    crashes = 0

    print(f"[*] Commencing statistical evaluation over {n_episodes} episodes...")

    for ep in range(n_episodes):
        obs, info = env.reset(seed=seed + ep)
        done = False
        truncated = False
        total_reward = 0.0
        length = 0

        while not (done or truncated):
            if is_custom_pytorch:
                obs_t = torch.tensor(obs, dtype=torch.float32, device=device).unsqueeze(0)
                with torch.no_grad():
                    if hasattr(model, "actor_mean"):  # Continuous
                        action = model.actor_mean(obs_t).squeeze(0).cpu().numpy()
                    elif hasattr(model, "actor"):  # Discrete
                        logits = model.actor(obs_t)
                        action = torch.argmax(logits, dim=-1).item()
                    elif hasattr(model, "agent"):
                        action, _, _, _ = model.agent.get_action_and_value(obs_t)
                        action = action.squeeze(0).cpu().numpy()
                    else:
                        raise ValueError("Unrecognized custom model structure")
            else:
                # Stable-Baselines3 model
                action, _ = model.predict(obs, deterministic=True)

            obs, reward, done, truncated, info = env.step(action)
            total_reward += reward
            length += 1

        episode_rewards.append(total_reward)
        episode_lengths.append(length)

        if total_reward >= 200.0:
            successes += 1
        elif total_reward <= -100.0:
            crashes += 1

    env.close()

    results = {
        "n_episodes": n_episodes,
        "mean_reward": float(np.mean(episode_rewards)),
        "std_reward": float(np.std(episode_rewards)),
        "median_reward": float(np.median(episode_rewards)),
        "min_reward": float(np.min(episode_rewards)),
        "max_reward": float(np.max(episode_rewards)),
        "success_rate_pct": float((successes / n_episodes) * 100.0),
        "crash_rate_pct": float((crashes / n_episodes) * 100.0),
        "mean_length": float(np.mean(episode_lengths)),
        "std_length": float(np.std(episode_lengths)),
        "rewards_raw": episode_rewards,
    }

    print("=" * 60)
    print("           MONTE CARLO EVALUATION SUMMARY           ")
    print("=" * 60)
    print(f" Episodes Evaluated    : {n_episodes}")
    print(f" Mean Return +/- Std     : {results['mean_reward']:.2f} +/- {results['std_reward']:.2f}")
    print(f" Median Return         : {results['median_reward']:.2f}")
    print(f" Min / Max Return      : {results['min_reward']:.2f} / {results['max_reward']:.2f}")
    print(f" Land Success Rate     : {results['success_rate_pct']:.1f}%")
    print(f" Crash Rate            : {results['crash_rate_pct']:.1f}%")
    print(f" Mean Episode Length   : {results['mean_length']:.1f} steps")
    print("=" * 60)

    return results
