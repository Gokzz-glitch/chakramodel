"""
Policy Evaluation & Benchmarking Suite for Vision-Guided Robotic Arm
"""

import os
import time
import numpy as np
import torch
from typing import Dict, Any, Union

from .robotic_arm_env import VisionGuidedPandaArmEnv


def benchmark_robotic_arm_policy(
    model: Any,
    config: dict,
    n_episodes: int = 50,
    seed: int = 42,
    device: str = "cpu",
    save_summary_path: str = "./logs/arm_evaluation_summary.txt",
) -> Dict[str, Union[float, int, list]]:
    """
    Executes rigorous evaluation across randomized 3D goal positions.
    """
    env = VisionGuidedPandaArmEnv(config=config, render_mode=None)
    final_errors_mm = []
    successes_30mm = 0
    successes_15mm = 0
    step_latencies_ms = []
    episode_lengths = []

    print(f"[*] Commencing Robotic Arm Policy Benchmark ({n_episodes} randomized trials)...")

    for ep in range(n_episodes):
        obs, info = env.reset(seed=seed + ep)
        done = False
        truncated = False
        step_count = 0
        final_dist = 1.0

        while not (done or truncated):
            rgb_t = torch.tensor(obs["rgb"], dtype=torch.float32, device=device).unsqueeze(0)
            proprio_t = torch.tensor(obs["proprioception"], dtype=torch.float32, device=device).unsqueeze(0)

            t0 = time.perf_counter()
            with torch.no_grad():
                if hasattr(model, "extract_features"):
                    features = model.extract_features(rgb_t, proprio_t)
                    action = model.actor_mean(features).squeeze(0).cpu().numpy()
                elif hasattr(model, "predict"):
                    action, _ = model.predict(obs, deterministic=True)
                else:
                    action, _, _, _ = model.get_action_and_value(rgb_t, proprio_t)
                    action = action.squeeze(0).cpu().numpy()
            t1 = time.perf_counter()
            step_latencies_ms.append((t1 - t0) * 1000.0)

            obs, reward, done, truncated, step_info = env.step(action)
            step_count += 1
            final_dist = step_info.get("euclidean_distance_m", 1.0)

        final_err_mm = float(final_dist * 1000.0)
        final_errors_mm.append(final_err_mm)
        episode_lengths.append(step_count)

        if final_err_mm <= 30.0:
            successes_30mm += 1
        if final_err_mm <= 15.0:
            successes_15mm += 1

    env.close()

    results = {
        "n_episodes": n_episodes,
        "mean_error_mm": float(np.mean(final_errors_mm)),
        "std_error_mm": float(np.std(final_errors_mm)),
        "median_error_mm": float(np.median(final_errors_mm)),
        "min_error_mm": float(np.min(final_errors_mm)),
        "max_error_mm": float(np.max(final_errors_mm)),
        "success_rate_30mm_pct": float((successes_30mm / n_episodes) * 100.0),
        "success_rate_15mm_pct": float((successes_15mm / n_episodes) * 100.0),
        "mean_step_latency_ms": float(np.mean(step_latencies_ms)),
        "inference_fps": float(1000.0 / np.mean(step_latencies_ms)),
        "mean_episode_steps": float(np.mean(episode_lengths)),
        "errors_raw": final_errors_mm,
    }

    report_str = f"""
=================================================================
      VISION-GUIDED ROBOTIC ARM BENCHMARK REPORT      
=================================================================
 Trials Evaluated            : {n_episodes}
 Mean Final Positioning Error: {results['mean_error_mm']:.2f} +/- {results['std_error_mm']:.2f} mm
 Median Error                : {results['median_error_mm']:.2f} mm
 Min / Max Error             : {results['min_error_mm']:.2f} mm / {results['max_error_mm']:.2f} mm
 Success Rate (<= 30mm)      : {results['success_rate_30mm_pct']:.1f}%
 High Precision (<= 15mm)    : {results['success_rate_15mm_pct']:.1f}%
 Mean Inference Latency      : {results['mean_step_latency_ms']:.2f} ms ({results['inference_fps']:.1f} FPS)
 Mean Episode Steps          : {results['mean_episode_steps']:.1f}
=================================================================
"""
    print(report_str)

    if save_summary_path:
        os.makedirs(os.path.dirname(save_summary_path), exist_ok=True)
        with open(save_summary_path, "w", encoding="utf-8") as f:
            f.write(report_str)
        print(f"[OK] Evaluation summary saved to: {save_summary_path}")

    return results
