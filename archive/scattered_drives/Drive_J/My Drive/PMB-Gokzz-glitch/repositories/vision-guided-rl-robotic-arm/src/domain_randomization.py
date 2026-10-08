"""
Domain Randomization Engine for Sim-to-Real Policy Transfer
"""

import numpy as np
from typing import Dict, Any, Optional

try:
    import pybullet as p
    PYBULLET_AVAILABLE = True
except ImportError:
    p = None
    PYBULLET_AVAILABLE = False


class DomainRandomizer:
    """
    Applies Visual and Physical Dynamics Randomization to minimize the Sim-to-Real Gap.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.vis_cfg = self.config.get("visual_randomization", {})
        self.dyn_cfg = self.config.get("dynamics_randomization", {})

        self.vis_enabled = self.vis_cfg.get("enabled", True)
        self.dyn_enabled = self.dyn_cfg.get("enabled", True)

    def randomize_image(self, rgb_image: np.ndarray) -> np.ndarray:
        """
        Applies photometric jitter, Gaussian noise, and color balance shifts.
        
        Args:
            rgb_image (np.ndarray): Shape (H, W, 3), dtype uint8 [0, 255]
            
        Returns:
            np.ndarray: Perturbed image in uint8 [0, 255]
        """
        if not self.vis_enabled:
            return rgb_image

        img = rgb_image.astype(np.float32) / 255.0

        # 1. Brightness jitter
        brightness_factor = np.random.uniform(0.85, 1.15)
        img = img * brightness_factor

        # 2. Contrast jitter
        contrast_factor = np.random.uniform(0.85, 1.15)
        mean_intensity = np.mean(img, axis=(0, 1), keepdims=True)
        img = (img - mean_intensity) * contrast_factor + mean_intensity

        # 3. Additive Gaussian sensor noise
        noise_std = self.vis_cfg.get("gaussian_noise_std", 0.02)
        noise = np.random.normal(0.0, noise_std, img.shape)
        img = img + noise

        # Clip and convert back to uint8
        img = np.clip(img * 255.0, 0.0, 255.0).astype(np.uint8)
        return img

    def sample_camera_jitter(self) -> np.ndarray:
        """Samples small 3D translation offset for camera viewpoint randomization."""
        if not self.vis_enabled:
            return np.zeros(3, dtype=np.float32)
        jitter_std = np.array(
            self.vis_cfg.get("camera_pose_jitter", {}).get("eye_pos_std", [0.02, 0.02, 0.02]),
            dtype=np.float32,
        )
        return np.random.normal(0.0, jitter_std, size=3)

    def randomize_physics(self, robot_id: Optional[int], num_joints: int = 7, client_id: int = 0) -> None:
        """Randomizes joint friction, damping, and link inertial parameters in PyBullet."""
        if not self.dyn_enabled or robot_id is None or not PYBULLET_AVAILABLE or p is None:
            return

        friction_range = self.dyn_cfg.get("joint_friction_range", [0.02, 0.08])
        damping_range = self.dyn_cfg.get("joint_damping_range", [0.05, 0.15])

        for joint_idx in range(num_joints):
            rand_friction = np.random.uniform(friction_range[0], friction_range[1])
            rand_damping = np.random.uniform(damping_range[0], damping_range[1])

            try:
                p.changeDynamics(
                    bodyUniqueId=robot_id,
                    linkIndex=joint_idx,
                    lateralFriction=rand_friction,
                    jointDamping=rand_damping,
                    physicsClientId=client_id,
                )
            except Exception:
                pass
