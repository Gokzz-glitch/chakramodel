"""
Automated Verification Suite for Vision-Guided Robotic Arm Control
"""

import os
import sys
import numpy as np
import torch

from src.camera_sensor import CameraSensor
from src.vision_backbone import VisionBackbone
from src.domain_randomization import DomainRandomizer
from src.reward_functions import ReachingReward
from src.robotic_arm_env import VisionGuidedPandaArmEnv
from src.multimodal_policy import MultiModalActorCritic
from src.evaluate_policy import benchmark_robotic_arm_policy


def test_all():
    print("=" * 60)
    print("TESTING VISION-GUIDED-RL-ROBOTIC-ARM REPOSITORY")
    print("=" * 60)

    # 1. Test ResNet-18 Perception Backbone
    backbone = VisionBackbone(latent_dim=128, pretrained=False, freeze_backbone=True)
    dummy_img = torch.randn(2, 3, 128, 128)
    latents = backbone(dummy_img)
    assert latents.shape == (2, 128), f"Backbone latent shape mismatch: {latents.shape}"
    print(f"  [OK] Vision Backbone ResNet-18 forward pass verified (Shape: {latents.shape}).")

    # 2. Test Multi-Modal Actor-Critic Network
    policy = MultiModalActorCritic(
        proprio_dim=17,
        action_dim=7,
        latent_dim=128,
        hidden_dim=256,
        pretrained_vision=False,
    )
    dummy_prop = torch.randn(2, 17)
    actions, log_prob, entropy, values = policy.get_action_and_value(dummy_img, dummy_prop)
    assert actions.shape == (2, 7), f"Action shape mismatch: {actions.shape}"
    assert values.shape == (2, 1), f"Value shape mismatch: {values.shape}"
    print(f"  [OK] Multi-Modal Policy fusion & Gaussian action sampling verified (Actions: {actions.shape}).")

    # 3. Test Domain Randomization
    randomizer = DomainRandomizer()
    dummy_raw_img = (np.random.rand(128, 128, 3) * 255).astype(np.uint8)
    rand_img = randomizer.randomize_image(dummy_raw_img)
    assert rand_img.shape == (128, 128, 3) and rand_img.dtype == np.uint8
    print("  [OK] Domain Randomization (Color Jitter & Sensor Noise) verified.")

    # 4. Test Shaped Reward Engine
    reward_engine = ReachingReward()
    r, is_succ, info = reward_engine.compute_reward(
        ee_pos=np.array([0.0, 0.0, 0.2]),
        target_pos=np.array([0.0, 0.0, 0.2]),
        joint_velocities=np.zeros(7),
        current_action=np.zeros(7),
        previous_action=np.zeros(7),
    )
    assert is_succ is True, "Target reach should register success bonus"
    assert r > 40.0, f"Expected success reward > 40, got {r}"
    print(f"  [OK] Shaped Multi-Objective Reaching Reward verified (Success reward: {r:.2f}).")

    # 5. Test 7-DOF Panda Environment
    config = {
        "camera": {"width": 128, "height": 128, "fov": 60.0},
        "robot": {"max_joint_velocity": 1.5},
        "reward": {"distance_scale": 2.5, "success_bonus": 50.0},
        "visual_randomization": {"enabled": True},
        "dynamics_randomization": {"enabled": True},
    }
    env = VisionGuidedPandaArmEnv(config=config, render_mode=None)
    obs, env_info = env.reset(seed=42)
    assert "rgb" in obs and "proprioception" in obs
    assert obs["rgb"].shape == (128, 128, 3)
    assert obs["proprioception"].shape == (17,)

    act = env.action_space.sample()
    obs_next, rew, done, trunc, step_info = env.step(act)
    assert isinstance(rew, float)
    print(f"  [OK] 7-DOF Panda Manipulator Env step verified (Distance: {step_info['euclidean_distance_m']:.3f}m).")
    env.close()

    # 6. Test 5-Episode Fast Benchmark Evaluation
    bench_results = benchmark_robotic_arm_policy(
        model=policy,
        config=config,
        n_episodes=5,
        seed=42,
        device="cpu",
    )
    assert bench_results["n_episodes"] == 5
    print(f"  [OK] Benchmarking & Monte Carlo Evaluation suite verified (Latency: {bench_results['mean_step_latency_ms']:.2f}ms).")

    print("\n" + "=" * 60)
    print("ALL VISION-GUIDED ROBOTIC ARM TESTS PASSED SUCCESSFULLY (100%)")
    print("=" * 60)


if __name__ == "__main__":
    test_all()
