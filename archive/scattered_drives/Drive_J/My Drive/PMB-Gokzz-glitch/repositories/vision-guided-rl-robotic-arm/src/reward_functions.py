"""
Reward Shaping and Objective Formulations for 7-DOF Robotic Manipulation
"""

import numpy as np
from typing import Dict, Any, Tuple


class ReachingReward:
    """
    Multi-objective reward function for robotic arm reach & precision targeting.
    """

    def __init__(
        self,
        distance_scale: float = 2.5,
        success_bonus: float = 50.0,
        success_threshold: float = 0.03,  # 30 mm
        velocity_penalty_weight: float = 0.005,
        action_smoothness_weight: float = 0.01,
    ):
        self.distance_scale = distance_scale
        self.success_bonus = success_bonus
        self.success_threshold = success_threshold
        self.velocity_penalty_weight = velocity_penalty_weight
        self.action_smoothness_weight = action_smoothness_weight

    def compute_reward(
        self,
        ee_pos: np.ndarray,
        target_pos: np.ndarray,
        joint_velocities: np.ndarray,
        current_action: np.ndarray,
        previous_action: np.ndarray,
    ) -> Tuple[float, bool, Dict[str, float]]:
        """
        Computes scalar shaped reward and success indicator.
        
        Returns:
            reward (float): Shaped reward
            is_success (bool): Whether end-effector is within target tolerance
            info (dict): Breakdown of constituent reward components
        """
        distance = np.linalg.norm(ee_pos - target_pos)

        # 1. Smooth bounded distance reward: R_dist = -tanh(k * d)
        r_dist = -np.tanh(self.distance_scale * distance)

        # 2. Success bonus
        is_success = bool(distance <= self.success_threshold)
        r_success = self.success_bonus if is_success else 0.0

        # 3. Energy / velocity damping penalty to discourage violent oscillations
        r_vel = -self.velocity_penalty_weight * np.sum(np.square(joint_velocities))

        # 4. Action smoothness penalty (penalizing high derivative of control signals)
        r_smooth = 0.0
        if previous_action is not None:
            r_smooth = -self.action_smoothness_weight * np.sum(np.square(current_action - previous_action))

        total_reward = float(r_dist + r_success + r_vel + r_smooth)

        breakdown = {
            "reward_distance": float(r_dist),
            "reward_success": float(r_success),
            "reward_velocity_penalty": float(r_vel),
            "reward_smoothness": float(r_smooth),
            "euclidean_distance_m": float(distance),
            "is_success": is_success,
        }

        return total_reward, is_success, breakdown
