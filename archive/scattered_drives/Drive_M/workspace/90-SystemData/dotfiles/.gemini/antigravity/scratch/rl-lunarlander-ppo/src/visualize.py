"""
Statistical Plotting and Video Rendering Suite for RL Rollouts
"""

import os
from typing import List, Optional
import numpy as np


def plot_reward_distribution(
    rewards: List[float],
    title: str = "PPO Training & Evaluation Reward Distribution",
    save_path: Optional[str] = "./logs/reward_distribution.png",
):
    """
    Plots and saves reward distribution histogram with mean and standard deviation.
    Includes graceful pure-python fallback if matplotlib backend is constrained.
    """
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

    mean_r = float(np.mean(rewards))
    std_r = float(np.std(rewards))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
        ax.hist(rewards, bins=15, color="#2ecc71", edgecolor="#27ae60", alpha=0.8, density=True)
        ax.axvline(mean_r, color="#e74c3c", linestyle="--", linewidth=2, label=f"Mean: {mean_r:.2f}")
        ax.axvline(mean_r + std_r, color="#f39c12", linestyle=":", linewidth=1.5, label=f"+/-1 Std: {std_r:.2f}")
        ax.axvline(mean_r - std_r, color="#f39c12", linestyle=":", linewidth=1.5)

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Cumulative Episode Reward", fontsize=10)
        ax.set_ylabel("Probability Density", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="upper left")

        if save_path:
            plt.savefig(save_path, bbox_inches="tight")
            plt.close(fig)
            print(f"[[OK]] Reward distribution plot saved to: {save_path}")
    except Exception as e:
        # Graceful text summary fallback if matplotlib DLL is unavailable
        print(f"[i] Matplotlib plot skipped ({e}). Summary metrics: Mean={mean_r:.2f}, Std={std_r:.2f}")
        if save_path:
            summary_txt = save_path.replace(".png", ".txt")
            with open(summary_txt, "w") as f:
                f.write(f"Benchmark Reward Distribution Summary\n")
                f.write(f"Mean Reward: {mean_r:.2f}\n")
                f.write(f"Std Reward : {std_r:.2f}\n")
                f.write(f"Raw Rewards: {rewards}\n")
            print(f"[[OK]] Reward statistics summary saved to: {summary_txt}")


def save_rollout_video(
    frames: List[np.ndarray],
    save_path: str = "./logs/lunarlander_rollout.mp4",
    fps: int = 30,
):
    """Saves a sequence of RGB rendering frames to MP4 or GIF."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    try:
        import imageio
        if save_path.endswith(".gif"):
            imageio.mimsave(save_path, frames, fps=fps, loop=0)
        else:
            try:
                imageio.mimsave(save_path, frames, fps=fps, macro_block_size=1)
            except Exception:
                gif_path = save_path.replace(".mp4", ".gif")
                imageio.mimsave(gif_path, frames, fps=fps)
                save_path = gif_path
        print(f"[[OK]] Video rendered and saved to: {save_path}")
    except Exception as e:
        print(f"[!] Warning: Video generation failed ({e})")
