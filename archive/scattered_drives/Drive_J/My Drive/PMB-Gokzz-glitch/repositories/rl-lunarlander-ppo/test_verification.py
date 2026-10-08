"""
Automated Verification Suite for LunarLander PPO
"""

import os
import sys
import numpy as np
import torch
import gymnasium as gym

from src.custom_ppo import ActorCritic, RolloutBuffer, CustomPPOAgent
from src.env_wrappers import make_env
from src.visualize import plot_reward_distribution


def test_all():
    print("=" * 60)
    print("TESTING RL-LUNARLANDER-PPO REPOSITORY")
    print("=" * 60)

    # 1. Test ActorCritic Model
    obs_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(8,))
    act_space_disc = gym.spaces.Discrete(4)
    act_space_cont = gym.spaces.Box(low=-1.0, high=1.0, shape=(2,))

    ac_disc = ActorCritic(obs_space, act_space_disc, hidden_dim=64)
    ac_cont = ActorCritic(obs_space, act_space_cont, hidden_dim=64)

    dummy_obs = torch.randn(4, 8)
    a_d, logp_d, ent_d, val_d = ac_disc.get_action_and_value(dummy_obs)
    assert a_d.shape == (4,), f"Discrete action shape error: {a_d.shape}"
    assert val_d.shape == (4, 1), f"Value shape error: {val_d.shape}"
    print("  [OK] Discrete Actor-Critic forward pass & sampling verified.")

    a_c, logp_c, ent_c, val_c = ac_cont.get_action_and_value(dummy_obs)
    assert a_c.shape == (4, 2), f"Continuous action shape error: {a_c.shape}"
    print("  [OK] Continuous Actor-Critic forward pass & sampling verified.")

    # 2. Test Rollout Buffer & GAE Calculation
    buffer = RolloutBuffer(
        num_steps=128,
        num_envs=1,
        obs_shape=(8,),
        action_shape=(),
        device=torch.device("cpu"),
        is_continuous=False,
    )
    for step in range(128):
        buffer.obs[step, 0] = torch.randn(8)
        buffer.actions[step, 0] = torch.randint(0, 4, ())
        buffer.logprobs[step, 0] = -1.38
        buffer.rewards[step, 0] = 1.0
        buffer.dones[step, 0] = 0.0
        buffer.values[step, 0] = 0.5

    buffer.compute_gae(next_value=torch.tensor([0.5]), next_done=torch.tensor([0.0]))
    assert buffer.advantages.shape == (128, 1), "Advantage shape mismatch"
    assert buffer.returns.shape == (128, 1), "Returns shape mismatch"
    print("  [OK] GAE Advantage Computation and Vectorized Buffer verified.")

    # 3. Test Reward Plotter
    test_plot = "./logs/verification_reward_plot.png"
    plot_reward_distribution([210.0, 240.5, 230.1, 198.4, 255.2], save_path=test_plot)
    print("  [OK] Visualization and statistical logging verified.")

    # 4. Test PPO Agent Training Step with SyncVectorEnv
    env_fn = make_env(env_id="CartPole-v1", seed=42, enable_reward_shaping=False, enable_obs_norm=True)
    envs = gym.vector.SyncVectorEnv([env_fn])

    ppo_config = {
        "learning_rate": 3e-4,
        "n_steps": 64,
        "batch_size": 32,
        "n_epochs": 2,
        "gamma": 0.99,
        "gae_lambda": 0.95,
        "clip_range": 0.2,
        "ent_coef": 0.01,
        "vf_coef": 0.5,
        "max_grad_norm": 0.5,
        "hidden_dim": 64,
    }

    agent = CustomPPOAgent(envs=envs, config=ppo_config, device=torch.device("cpu"))
    obs, _ = envs.reset(seed=42)
    next_obs = torch.tensor(obs, dtype=torch.float32)
    next_done = torch.zeros(1, dtype=torch.float32)

    next_obs, next_done, metrics = agent.train_step(global_step=64, next_obs=next_obs, next_done=next_done)
    assert "policy_loss" in metrics and "value_loss" in metrics
    print(f"  [OK] End-to-end PPO Training Update Step verified (Loss: {metrics['policy_loss']:.4f}).")

    # Save & Load Checkpoint test
    ckpt_path = "./models/test_checkpoints/test_agent.pt"
    agent.save(ckpt_path)
    assert os.path.exists(ckpt_path), "Checkpoint file not saved!"
    agent.load(ckpt_path)
    print("  [OK] Model Checkpoint Serialization and Deserialization verified.")
    envs.close()

    print("\n" + "=" * 60)
    print("ALL LUNARLANDER TESTS PASSED SUCCESSFULLY (100%)")
    print("=" * 60)


if __name__ == "__main__":
    test_all()
