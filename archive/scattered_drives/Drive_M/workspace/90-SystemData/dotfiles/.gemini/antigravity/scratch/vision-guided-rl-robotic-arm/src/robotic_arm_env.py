"""
Gymnasium-Compliant 7-DOF Franka Panda Robotic Arm Simulation Environment
"""

import os
import time
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Optional, Dict, Any, Tuple

try:
    import pybullet as p
    import pybullet_data
    PYBULLET_AVAILABLE = True
except ImportError:
    p = None
    pybullet_data = None
    PYBULLET_AVAILABLE = False

from .camera_sensor import CameraSensor
from .domain_randomization import DomainRandomizer
from .reward_functions import ReachingReward


class VisionGuidedPandaArmEnv(gym.Env):
    """
    Vision-guided 7-DOF Franka Emika Panda Robotic Manipulator Environment.
    Supports both PyBullet dynamic physics engine and high-fidelity kinematic simulation.
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        render_mode: Optional[str] = None,
    ):
        super().__init__()
        self.config = config or {}
        self.render_mode = render_mode

        # Physics client connection
        self.client_id = 0
        self.use_pybullet = False

        if PYBULLET_AVAILABLE and p is not None:
            try:
                if self.render_mode == "human":
                    self.client_id = p.connect(p.GUI)
                    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0, physicsClientId=self.client_id)
                else:
                    self.client_id = p.connect(p.DIRECT)
                p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.client_id)
                p.setGravity(0, 0, -9.81, physicsClientId=self.client_id)
                self.use_pybullet = True
            except Exception:
                self.use_pybullet = False

        # Robot specifications
        self.dof = 7
        self.max_episode_steps = 100
        self.current_step = 0
        self.robot_id = None
        self.target_id = None
        self.joint_positions = np.zeros(self.dof, dtype=np.float32)
        self.joint_velocities = np.zeros(self.dof, dtype=np.float32)

        # Workspace limits for target reaching
        self.workspace_min = np.array([-0.25, -0.25, 0.10], dtype=np.float32)
        self.workspace_max = np.array([0.25, 0.25, 0.45], dtype=np.float32)

        # Camera Sensor
        cam_cfg = self.config.get("camera", {})
        self.camera = CameraSensor(
            width=cam_cfg.get("width", 128),
            height=cam_cfg.get("height", 128),
            fov=cam_cfg.get("fov", 60.0),
            camera_eye=cam_cfg.get("camera_eye", (0.6, 0.0, 0.5)),
            camera_target=cam_cfg.get("camera_target", (0.0, 0.0, 0.1)),
            physics_client_id=self.client_id,
        )

        # Domain Randomizer & Reward Engine
        self.randomizer = DomainRandomizer(self.config)
        rew_cfg = self.config.get("reward", {})
        self.reward_engine = ReachingReward(
            distance_scale=rew_cfg.get("distance_scale", 2.5),
            success_bonus=rew_cfg.get("success_bonus", 50.0),
            success_threshold=rew_cfg.get("success_threshold", 0.03),
            velocity_penalty_weight=rew_cfg.get("velocity_penalty_weight", 0.005),
            action_smoothness_weight=rew_cfg.get("action_smoothness_weight", 0.01),
        )

        # Action Space: 7 continuous joint velocity commands in [-1.0, 1.0]
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(self.dof,), dtype=np.float32
        )

        # Observation Space: Dict containing raw RGB visual stream + 7-DOF proprioception
        self.observation_space = spaces.Dict(
            {
                "rgb": spaces.Box(
                    low=0, high=255, shape=(cam_cfg.get("height", 128), cam_cfg.get("width", 128), 3), dtype=np.uint8
                ),
                "proprioception": spaces.Box(
                    low=-np.inf, high=np.inf, shape=(17,), dtype=np.float32  # 7 pos + 7 vel + 3 ee_pos
                ),
            }
        )

        self.prev_action = None
        self.target_pos = np.zeros(3, dtype=np.float32)
        if self.use_pybullet:
            self._load_scene()

    def _load_scene(self):
        """Loads URDF models into PyBullet."""
        p.resetSimulation(physicsClientId=self.client_id)
        p.setGravity(0, 0, -9.81, physicsClientId=self.client_id)
        p.loadURDF("plane.urdf", [0, 0, -0.65], physicsClientId=self.client_id)
        p.loadURDF("table/table.urdf", [0, 0, -0.65], physicsClientId=self.client_id)
        self.robot_id = p.loadURDF("franka_panda/panda.urdf", [0, -0.4, 0.0], useFixedBase=True, physicsClientId=self.client_id)

        visual_shape_id = p.createVisualShape(
            shapeType=p.GEOM_SPHERE, radius=0.025, rgbaColor=[0.9, 0.1, 0.1, 0.9], physicsClientId=self.client_id
        )
        self.target_id = p.createMultiBody(
            baseVisualShapeIndex=visual_shape_id, basePosition=[0, 0, 0.2], physicsClientId=self.client_id
        )

    def _forward_kinematics(self, q: np.ndarray) -> np.ndarray:
        """7-DOF Franka Panda geometric forward kinematics."""
        # Link lengths
        d1, d3, d5, d7 = 0.333, 0.316, 0.384, 0.107
        a4, a7 = 0.0825, 0.088

        # Simplified kinematic position mapping
        x = np.sin(q[0]) * (d3 * np.cos(q[1]) + d5 * np.cos(q[3]) + a7 * np.cos(q[5]))
        y = np.cos(q[0]) * (d3 * np.cos(q[1]) + d5 * np.cos(q[3]) + a7 * np.cos(q[5])) - 0.4
        z = d1 + d3 * np.sin(q[1]) - d5 * np.sin(q[3]) + a7 * np.sin(q[5])
        return np.array([x, y, z], dtype=np.float32)

    def _get_ee_position(self) -> np.ndarray:
        """Retrieves 3D cartesian coordinates of end-effector."""
        if self.use_pybullet and self.robot_id is not None:
            ee_state = p.getLinkState(self.robot_id, 7, physicsClientId=self.client_id)
            return np.array(ee_state[0], dtype=np.float32)
        return self._forward_kinematics(self.joint_positions)

    def _get_proprioceptive_state(self) -> np.ndarray:
        """Collects 7 joint positions, 7 joint velocities, and 3D end-effector coordinate."""
        if self.use_pybullet and self.robot_id is not None:
            joint_states = p.getJointStates(self.robot_id, range(self.dof), physicsClientId=self.client_id)
            q = np.array([st[0] for st in joint_states], dtype=np.float32)
            dq = np.array([st[1] for st in joint_states], dtype=np.float32)
        else:
            q = self.joint_positions.copy()
            dq = self.joint_velocities.copy()

        ee_pos = self._get_ee_position()
        return np.concatenate([q, dq, ee_pos], dtype=np.float32)

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        super().reset(seed=seed)
        self.current_step = 0
        self.prev_action = np.zeros(self.dof, dtype=np.float32)

        default_joints = np.array([0.0, -0.6, 0.0, -2.2, 0.0, 1.8, 0.8], dtype=np.float32)
        self.joint_positions = default_joints.copy()
        self.joint_velocities = np.zeros(self.dof, dtype=np.float32)

        # Sample randomized target position in 3D operational workspace
        self.target_pos = np.random.uniform(self.workspace_min, self.workspace_max).astype(np.float32)

        if self.use_pybullet and self.robot_id is not None:
            for idx, angle in enumerate(default_joints):
                p.resetJointState(self.robot_id, idx, angle, targetVelocity=0.0, physicsClientId=self.client_id)
            p.resetBasePositionAndOrientation(self.target_id, self.target_pos.tolist(), [0, 0, 0, 1], physicsClientId=self.client_id)
            self.randomizer.randomize_physics(self.robot_id, num_joints=self.dof, client_id=self.client_id)
            for _ in range(5):
                p.stepSimulation(physicsClientId=self.client_id)

        camera_jitter = self.randomizer.sample_camera_jitter()
        ee_pos = self._get_ee_position()
        rgb, _ = self.camera.render(eye_jitter=camera_jitter, ee_pos=ee_pos, target_pos=self.target_pos)
        rgb_randomized = self.randomizer.randomize_image(rgb)
        proprio = self._get_proprioceptive_state()

        obs = {"rgb": rgb_randomized, "proprioception": proprio}
        info = {"target_position": self.target_pos}
        return obs, info

    def step(
        self, action: np.ndarray
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        self.current_step += 1
        action = np.clip(action, -1.0, 1.0)
        dt = 0.05
        max_vel = self.config.get("robot", {}).get("max_joint_velocity", 1.5)
        scaled_vel = action * max_vel

        if self.use_pybullet and self.robot_id is not None:
            p.setJointMotorControlArray(
                bodyUniqueId=self.robot_id,
                jointIndices=list(range(self.dof)),
                controlMode=p.VELOCITY_CONTROL,
                targetVelocities=scaled_vel.tolist(),
                physicsClientId=self.client_id,
            )
            p.stepSimulation(physicsClientId=self.client_id)
        else:
            self.joint_velocities = scaled_vel
            self.joint_positions += self.joint_velocities * dt
            # Clip joint limits
            self.joint_positions = np.clip(self.joint_positions, -2.8, 2.8)

        ee_pos = self._get_ee_position()
        proprio = self._get_proprioceptive_state()
        joint_vels = proprio[7:14]

        reward, is_success, reward_info = self.reward_engine.compute_reward(
            ee_pos=ee_pos,
            target_pos=self.target_pos,
            joint_velocities=joint_vels,
            current_action=action,
            previous_action=self.prev_action,
        )
        self.prev_action = action.copy()

        terminated = bool(is_success)
        truncated = bool(self.current_step >= self.max_episode_steps)

        camera_jitter = self.randomizer.sample_camera_jitter()
        rgb, _ = self.camera.render(eye_jitter=camera_jitter, ee_pos=ee_pos, target_pos=self.target_pos)
        rgb_randomized = self.randomizer.randomize_image(rgb)

        obs = {"rgb": rgb_randomized, "proprioception": proprio}
        info = {**reward_info, "step": self.current_step}
        return obs, reward, terminated, truncated, info

    def render(self) -> Optional[np.ndarray]:
        ee_pos = self._get_ee_position()
        rgb, _ = self.camera.render(shadow=1, ee_pos=ee_pos, target_pos=self.target_pos)
        return rgb

    def close(self):
        if self.use_pybullet and p is not None and p.isConnected(physicsClientId=self.client_id):
            p.disconnect(physicsClientId=self.client_id)
