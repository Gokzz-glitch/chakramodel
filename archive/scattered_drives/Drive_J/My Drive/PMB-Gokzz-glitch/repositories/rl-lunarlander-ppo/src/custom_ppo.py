"""
Pure PyTorch Implementation of Proximal Policy Optimization (PPO)
from First Principles.
"""

import os
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions.categorical import Categorical
from torch.distributions.normal import Normal
from typing import Tuple, Dict, Any, Optional
import gymnasium as gym


def layer_init(layer: nn.Linear, std: float = np.sqrt(2), bias_const: float = 0.0) -> nn.Linear:
    """Orthogonal parameter initialization with constant bias."""
    nn.init.orthogonal_(layer.weight, std)
    nn.init.constant_(layer.bias, bias_const)
    return layer


class ActorCritic(nn.Module):
    """
    Dual-head Actor-Critic Neural Network supporting both Discrete
    and Continuous action spaces.
    """

    def __init__(
        self,
        observation_space: gym.spaces.Box,
        action_space: gym.spaces.Space,
        hidden_dim: int = 128,
    ):
        super().__init__()
        self.is_continuous = isinstance(action_space, gym.spaces.Box)
        obs_dim = int(np.prod(observation_space.shape))

        # Critic (Value Network)
        self.critic = nn.Sequential(
            layer_init(nn.Linear(obs_dim, hidden_dim)),
            nn.Tanh(),
            layer_init(nn.Linear(hidden_dim, hidden_dim)),
            nn.Tanh(),
            layer_init(nn.Linear(hidden_dim, 1), std=1.0),
        )

        # Actor (Policy Network)
        if self.is_continuous:
            act_dim = int(np.prod(action_space.shape))
            self.actor_mean = nn.Sequential(
                layer_init(nn.Linear(obs_dim, hidden_dim)),
                nn.Tanh(),
                layer_init(nn.Linear(hidden_dim, hidden_dim)),
                nn.Tanh(),
                layer_init(nn.Linear(hidden_dim, act_dim), std=0.01),
            )
            # Learnable state-independent log standard deviation parameter
            self.actor_logstd = nn.Parameter(torch.zeros(1, act_dim))
        else:
            act_dim = action_space.n
            self.actor = nn.Sequential(
                layer_init(nn.Linear(obs_dim, hidden_dim)),
                nn.Tanh(),
                layer_init(nn.Linear(hidden_dim, hidden_dim)),
                nn.Tanh(),
                layer_init(nn.Linear(hidden_dim, act_dim), std=0.01),
            )

    def get_value(self, x: torch.Tensor) -> torch.Tensor:
        """Compute state value estimate V(s)."""
        return self.critic(x)

    def get_action_and_value(
        self,
        x: torch.Tensor,
        action: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Sample action from policy, evaluate log-probability, entropy, and state value.
        """
        if self.is_continuous:
            action_mean = self.actor_mean(x)
            action_logstd = self.actor_logstd.expand_as(action_mean)
            action_std = torch.exp(action_logstd)
            probs = Normal(action_mean, action_std)
            if action is None:
                action = probs.sample()
            log_prob = probs.log_prob(action).sum(axis=-1)
            entropy = probs.entropy().sum(axis=-1)
        else:
            logits = self.actor(x)
            probs = Categorical(logits=logits)
            if action is None:
                action = probs.sample()
            log_prob = probs.log_prob(action)
            entropy = probs.entropy()

        value = self.critic(x)
        return action, log_prob, entropy, value


class RolloutBuffer:
    """Storage buffer for vectorized on-policy rollouts."""

    def __init__(
        self,
        num_steps: int,
        num_envs: int,
        obs_shape: tuple,
        action_shape: tuple,
        device: torch.device,
        is_continuous: bool = False,
    ):
        self.num_steps = num_steps
        self.num_envs = num_envs
        self.device = device
        self.is_continuous = is_continuous

        self.obs = torch.zeros((num_steps, num_envs) + obs_shape, dtype=torch.float32, device=device)
        act_dtype = torch.float32 if is_continuous else torch.long
        self.actions = torch.zeros((num_steps, num_envs) + action_shape, dtype=act_dtype, device=device)
        self.logprobs = torch.zeros((num_steps, num_envs), dtype=torch.float32, device=device)
        self.rewards = torch.zeros((num_steps, num_envs), dtype=torch.float32, device=device)
        self.dones = torch.zeros((num_steps, num_envs), dtype=torch.float32, device=device)
        self.values = torch.zeros((num_steps, num_envs), dtype=torch.float32, device=device)

        self.advantages = torch.zeros((num_steps, num_envs), dtype=torch.float32, device=device)
        self.returns = torch.zeros((num_steps, num_envs), dtype=torch.float32, device=device)

    def compute_gae(
        self,
        next_value: torch.Tensor,
        next_done: torch.Tensor,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
    ) -> None:
        """Generalized Advantage Estimation (GAE-\lambda) calculation."""
        lastgaelam = 0.0
        for t in reversed(range(self.num_steps)):
            if t == self.num_steps - 1:
                nextnonterminal = 1.0 - next_done.float().view(self.num_envs)
                nextvalues = next_value.view(self.num_envs)
            else:
                nextnonterminal = 1.0 - self.dones[t + 1].view(self.num_envs)
                nextvalues = self.values[t + 1].view(self.num_envs)

            # Temporal Difference Error: delta = r + gamma * V(s_{t+1}) - V(s_t)
            delta = self.rewards[t] + gamma * nextvalues * nextnonterminal - self.values[t]
            # Advantage recursive formulation
            self.advantages[t] = lastgaelam = (
                delta + gamma * gae_lambda * nextnonterminal * lastgaelam
            )
        self.returns = self.advantages + self.values


class CustomPPOAgent:
    """
    PPO Algorithm Engine executing training epochs, mini-batch updates,
    and advantage calculations.
    """

    def __init__(
        self,
        envs: gym.vector.VectorEnv,
        config: Dict[str, Any],
        device: torch.device = torch.device("cpu"),
    ):
        self.envs = envs
        self.config = config
        self.device = device

        self.lr = config.get("learning_rate", 3e-4)
        self.num_steps = config.get("n_steps", 1024)
        self.num_envs = envs.num_envs
        self.batch_size = self.num_envs * self.num_steps
        self.minibatch_size = config.get("batch_size", 64)
        self.num_minibatches = self.batch_size // self.minibatch_size
        self.update_epochs = config.get("n_epochs", 4)
        self.gamma = config.get("gamma", 0.99)
        self.gae_lambda = config.get("gae_lambda", 0.95)
        self.clip_coef = config.get("clip_range", 0.2)
        self.ent_coef = config.get("ent_coef", 0.01)
        self.vf_coef = config.get("vf_coef", 0.5)
        self.max_grad_norm = config.get("max_grad_norm", 0.5)
        self.target_kl = config.get("target_kl", 0.015)

        # Initialize network
        single_obs_space = envs.single_observation_space
        single_act_space = envs.single_action_space
        self.is_continuous = isinstance(single_act_space, gym.spaces.Box)

        self.agent = ActorCritic(
            single_obs_space,
            single_act_space,
            hidden_dim=config.get("hidden_dim", 128),
        ).to(device)

        self.optimizer = optim.Adam(self.agent.parameters(), lr=self.lr, eps=1e-5)

        act_shape = single_act_space.shape if self.is_continuous else ()
        self.buffer = RolloutBuffer(
            self.num_steps,
            self.num_envs,
            single_obs_space.shape,
            act_shape,
            device,
            self.is_continuous,
        )

    def train_step(
        self,
        global_step: int,
        next_obs: torch.Tensor,
        next_done: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, float]]:
        """Collects on-policy rollout and updates actor-critic networks."""
        # 1. Rollout Phase
        for step in range(self.num_steps):
            self.buffer.obs[step] = next_obs
            self.buffer.dones[step] = next_done

            with torch.no_grad():
                action, logprob, _, value = self.agent.get_action_and_value(next_obs)
                self.buffer.values[step] = value.squeeze(-1)

            self.buffer.actions[step] = action
            self.buffer.logprobs[step] = logprob

            # Step vectorized environment
            cpu_action = action.cpu().numpy()
            obs, reward, terminations, truncations, infos = self.envs.step(cpu_action)
            dones = np.logical_or(terminations, truncations)

            self.buffer.rewards[step] = torch.tensor(reward, dtype=torch.float32, device=self.device)
            next_obs = torch.tensor(obs, dtype=torch.float32, device=self.device)
            next_done = torch.tensor(dones, dtype=torch.float32, device=self.device)

        # 2. Advantage Computation (GAE)
        with torch.no_grad():
            next_value = self.agent.get_value(next_obs)
            self.buffer.compute_gae(next_value, next_done, self.gamma, self.gae_lambda)

        # 3. Flatten rollouts for mini-batch updates
        b_obs = self.buffer.obs.reshape((-1,) + self.envs.single_observation_space.shape)
        act_dim = self.envs.single_action_space.shape if self.is_continuous else ()
        b_actions = self.buffer.actions.reshape((-1,) + act_dim)
        b_logprobs = self.buffer.logprobs.reshape(-1)
        b_advantages = self.buffer.advantages.reshape(-1)
        b_returns = self.buffer.returns.reshape(-1)
        b_values = self.buffer.values.reshape(-1)

        # Normalize advantages
        b_advantages = (b_advantages - b_advantages.mean()) / (b_advantages.std() + 1e-8)

        # 4. Optimization Epochs
        b_inds = np.arange(self.batch_size)
        clipfracs = []

        for epoch in range(self.update_epochs):
            np.random.shuffle(b_inds)
            for start in range(0, self.batch_size, self.minibatch_size):
                end = start + self.minibatch_size
                mb_inds = b_inds[start:end]

                _, newlogprob, entropy, newvalue = self.agent.get_action_and_value(
                    b_obs[mb_inds], b_actions[mb_inds]
                )
                logratio = newlogprob - b_logprobs[mb_inds]
                ratio = logratio.exp()

                with torch.no_grad():
                    approx_kl = ((ratio - 1) - logratio).mean()
                    clipfracs += [((ratio - 1.0).abs() > self.clip_coef).float().mean().item()]

                mb_advantages = b_advantages[mb_inds]

                # Policy Loss (Clipped Objective)
                pg_loss1 = -mb_advantages * ratio
                pg_loss2 = -mb_advantages * torch.clamp(
                    ratio, 1 - self.clip_coef, 1 + self.clip_coef
                )
                pg_loss = torch.max(pg_loss1, pg_loss2).mean()

                # Value Loss
                newvalue = newvalue.view(-1)
                v_loss = 0.5 * ((newvalue - b_returns[mb_inds]) ** 2).mean()

                # Entropy Bonus
                entropy_loss = entropy.mean()

                # Total Loss
                loss = pg_loss - self.ent_coef * entropy_loss + self.vf_coef * v_loss

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.agent.parameters(), self.max_grad_norm)
                self.optimizer.step()

            if self.target_kl is not None and approx_kl > self.target_kl:
                break

        metrics = {
            "policy_loss": pg_loss.item(),
            "value_loss": v_loss.item(),
            "entropy": entropy_loss.item(),
            "approx_kl": approx_kl.item(),
            "clipfrac": np.mean(clipfracs),
        }
        return next_obs, next_done, metrics

    def save(self, filepath: str) -> None:
        """Save model state dictionary."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        torch.save(
            {
                "model_state_dict": self.agent.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "config": self.config,
            },
            filepath,
        )

    def load(self, filepath: str) -> None:
        """Load model state dictionary."""
        checkpoint = torch.load(filepath, map_location=self.device)
        self.agent.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
