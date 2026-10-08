"""
Stable-Baselines3 PPO Training & Evaluation Pipeline
"""

import os
from typing import Dict, Any, Optional
import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    EvalCallback,
    CheckpointCallback,
    CallbackList,
)
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv, VecNormalize
from .env_wrappers import make_env


def create_vectorized_envs(
    env_id: str,
    n_envs: int = 8,
    continuous: bool = False,
    seed: int = 42,
    normalize_obs: bool = True,
    normalize_reward: bool = False,
    shape_reward: bool = False,
):
    """Creates parallel vectorized environments using SubprocVecEnv or DummyVecEnv."""
    env_fns = [
        make_env(
            env_id=env_id,
            continuous=continuous,
            seed=seed,
            idx=i,
            shape_reward=shape_reward,
        )
        for i in range(n_envs)
    ]
    vec_env = DummyVecEnv(env_fns) if n_envs == 1 else SubprocVecEnv(env_fns)
    if normalize_obs or normalize_reward:
        vec_env = VecNormalize(
            vec_env,
            norm_obs=normalize_obs,
            norm_reward=normalize_reward,
            clip_obs=10.0,
        )
    return vec_env


def train_sb3_ppo(
    config: Dict[str, Any],
    log_dir: str = "./logs/ppo_sb3",
    model_save_dir: str = "./models/sb3_checkpoints",
) -> PPO:
    """Configures and runs full training cycle with Stable-Baselines3 PPO."""
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(model_save_dir, exist_ok=True)

    env_cfg = config.get("environment", {})
    ppo_cfg = config.get("ppo", {})
    train_cfg = config.get("training", {})

    # Create training and evaluation vectorized environments
    env_id = env_cfg.get("env_id", "LunarLander-v2")
    continuous = env_cfg.get("continuous", False)
    num_envs = env_cfg.get("num_envs", 8)
    seed = env_cfg.get("seed", 42)

    train_env = create_vectorized_envs(
        env_id=env_id,
        n_envs=num_envs,
        continuous=continuous,
        seed=seed,
        normalize_obs=env_cfg.get("normalize_obs", True),
    )

    eval_env = create_vectorized_envs(
        env_id=env_id,
        n_envs=4,
        continuous=continuous,
        seed=seed + 100,
        normalize_obs=env_cfg.get("normalize_obs", True),
    )

    # Policy keyword arguments
    net_arch = config.get("network", {}).get("net_arch", {"pi": [128, 128], "vf": [128, 128]})
    policy_kwargs = dict(
        net_arch=net_arch,
        ortho_init=config.get("network", {}).get("ortho_init", True),
    )

    # Initialize PPO model
    model = PPO(
        policy="MlpPolicy",
        env=train_env,
        learning_rate=ppo_cfg.get("learning_rate", 3e-4),
        n_steps=ppo_cfg.get("n_steps", 1024),
        batch_size=ppo_cfg.get("batch_size", 64),
        n_epochs=ppo_cfg.get("n_epochs", 4),
        gamma=ppo_cfg.get("gamma", 0.999),
        gae_lambda=ppo_cfg.get("gae_lambda", 0.98),
        clip_range=ppo_cfg.get("clip_range", 0.2),
        ent_coef=ppo_cfg.get("ent_coef", 0.01),
        vf_coef=ppo_cfg.get("vf_coef", 0.5),
        max_grad_norm=ppo_cfg.get("max_grad_norm", 0.5),
        policy_kwargs=policy_kwargs,
        tensorboard_log=log_dir,
        verbose=1,
        seed=seed,
    )

    # Callbacks
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=os.path.join(model_save_dir, "best_model"),
        log_path=log_dir,
        eval_freq=train_cfg.get("eval_freq", 10000) // num_envs,
        n_eval_episodes=train_cfg.get("n_eval_episodes", 20),
        deterministic=True,
        render=False,
    )

    checkpoint_callback = CheckpointCallback(
        save_freq=train_cfg.get("save_freq", 50000) // num_envs,
        save_path=os.path.join(model_save_dir, "checkpoints"),
        name_prefix="ppo_lunarlander",
    )

    callback_list = CallbackList([eval_callback, checkpoint_callback])

    # Learn
    total_timesteps = train_cfg.get("total_timesteps", 500000)
    print(f"[*] Commencing SB3 PPO training for {total_timesteps} timesteps on {num_envs} vectorized envs...")
    model.learn(total_timesteps=total_timesteps, callback=callback_list, progress_bar=True)

    # Save final model
    final_path = os.path.join(model_save_dir, "final_model.zip")
    model.save(final_path)
    print(f"[[OK]] Training complete. Final model saved to: {final_path}")

    train_env.close()
    eval_env.close()
    return model
