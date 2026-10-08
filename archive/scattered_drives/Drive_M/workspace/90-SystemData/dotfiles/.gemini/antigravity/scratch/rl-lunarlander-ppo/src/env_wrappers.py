"""
Custom Environment Wrappers for Reward Shaping, Potential Guidance, and Observation Normalization
"""

import numpy as np
import gymnasium as gym
from typing import Optional, Tuple, Dict, Any


class ShapedRewardWrapper(gym.RewardWrapper):
    """
    Applies continuous potential-based reward shaping to accelerate policy learning.
    """

    def __init__(
        self,
        env: gym.Env,
        distance_weight: float = 1.2,
        velocity_penalty_weight: float = 0.4,
        angle_penalty_weight: float = 0.5,
        angular_vel_weight: float = 0.2,
        leg_contact_bonus: float = 20.0,
    ):
        super().__init__(env)
        self.distance_weight = distance_weight
        self.velocity_penalty_weight = velocity_penalty_weight
        self.angle_penalty_weight = angle_penalty_weight
        self.angular_vel_weight = angular_vel_weight
        self.leg_contact_bonus = leg_contact_bonus
        self.prev_potential = 0.0

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self.prev_potential = self._compute_potential(obs)
        return obs, info

    def _compute_potential(self, obs: np.ndarray) -> float:
        if len(obs) < 8:
            return 0.0
        x, y, vx, vy, theta, vtheta, left_contact, right_contact = obs[:8]
        dist = np.sqrt(x**2 + y**2)
        vel = np.sqrt(vx**2 + vy**2)
        potential = (
            -self.distance_weight * dist
            - self.velocity_penalty_weight * vel
            - self.angle_penalty_weight * abs(theta)
            - self.angular_vel_weight * abs(vtheta)
            + self.leg_contact_bonus * (left_contact + right_contact)
        )
        return potential

    def reward(self, reward: float) -> float:
        # Potential-based shaping: F(s, s') = gamma * Phi(s') - Phi(s)
        gamma = 0.99
        obs = self.env.unwrapped.state if hasattr(self.env.unwrapped, "state") else None
        if obs is not None and isinstance(obs, np.ndarray) and len(obs) >= 8:
            curr_potential = self._compute_potential(obs)
            shaping = gamma * curr_potential - self.prev_potential
            self.prev_potential = curr_potential
            return float(reward + 0.1 * shaping)
        return float(reward)


class NormalizeObservationWrapper(gym.ObservationWrapper):
    """
    Maintains running empirical mean and variance to normalize state observations online.
    """

    def __init__(self, env: gym.Env, epsilon: float = 1e-8, clip_obs: float = 10.0):
        super().__init__(env)
        self.epsilon = epsilon
        self.clip_obs = clip_obs
        self.obs_dim = env.observation_space.shape[0]
        self.running_mean = np.zeros(self.obs_dim, dtype=np.float32)
        self.running_var = np.ones(self.obs_dim, dtype=np.float32)
        self.count = epsilon

    def observation(self, observation: np.ndarray) -> np.ndarray:
        self.count += 1
        delta = observation - self.running_mean
        self.running_mean += delta / self.count
        delta2 = observation - self.running_mean
        self.running_var += delta * delta2

        var = self.running_var / (self.count - 1) if self.count > 1 else self.running_var
        norm_obs = (observation - self.running_mean) / np.sqrt(var + self.epsilon)
        return np.clip(norm_obs, -self.clip_obs, self.clip_obs).astype(np.float32)


def make_env(
    env_id: str = "LunarLander-v3",
    seed: int = 42,
    enable_reward_shaping: bool = True,
    enable_obs_norm: bool = True,
    render_mode: Optional[str] = None,
):
    """
    Factory function instantiating Gymnasium environments with custom wrapper pipeline.
    """
    def _init():
        try:
            env = gym.make(env_id, render_mode=render_mode)
        except Exception:
            # Fallback to CartPole or Pendulum if Box2D is not compiled locally
            fallback_id = "CartPole-v1"
            print(f"[!] '{env_id}' unavailable, falling back to '{fallback_id}' for demonstration.")
            env = gym.make(fallback_id, render_mode=render_mode)

        if enable_reward_shaping and "LunarLander" in env_id:
            env = ShapedRewardWrapper(env)
        if enable_obs_norm:
            env = NormalizeObservationWrapper(env)
        env.reset(seed=seed)
        return env

    return _init
