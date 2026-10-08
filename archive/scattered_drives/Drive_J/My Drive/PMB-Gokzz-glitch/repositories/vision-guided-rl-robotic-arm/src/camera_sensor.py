"""
Synthetic RGB-D Camera Sensor Interface for Robotic Perception
"""

import numpy as np
from typing import Tuple, Optional

try:
    import pybullet as p
    PYBULLET_AVAILABLE = True
except ImportError:
    p = None
    PYBULLET_AVAILABLE = False


class CameraSensor:
    """
    Synthetic Eye-to-Hand / Eye-in-Hand Camera Sensor.
    Computes camera view and projection matrices and captures RGB and Depth streams.
    """

    def __init__(
        self,
        width: int = 128,
        height: int = 128,
        fov: float = 60.0,
        near_val: float = 0.1,
        far_val: float = 2.0,
        camera_eye: Tuple[float, float, float] = (0.6, 0.0, 0.5),
        camera_target: Tuple[float, float, float] = (0.0, 0.0, 0.1),
        up_vector: Tuple[float, float, float] = (0.0, 0.0, 1.0),
        physics_client_id: int = 0,
    ):
        self.width = width
        self.height = height
        self.fov = fov
        self.near_val = near_val
        self.far_val = far_val
        self.camera_eye = np.array(camera_eye, dtype=np.float32)
        self.camera_target = np.array(camera_target, dtype=np.float32)
        self.up_vector = np.array(up_vector, dtype=np.float32)
        self.client_id = physics_client_id
        self.aspect = float(self.width) / float(self.height)

    def render(
        self,
        eye_jitter: Optional[np.ndarray] = None,
        shadow: int = 1,
        ee_pos: Optional[np.ndarray] = None,
        target_pos: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Renders an RGB and Depth frame from the camera's optical frame.

        Returns:
            rgb_image (np.ndarray): Shape (H, W, 3) uint8 [0, 255]
            depth_image (np.ndarray): Shape (H, W) float32 in meters
        """
        eye_pos = self.camera_eye.copy()
        if eye_jitter is not None:
            eye_pos += eye_jitter

        if PYBULLET_AVAILABLE and p is not None and p.isConnected(physicsClientId=self.client_id):
            view_matrix = p.computeViewMatrix(
                cameraEyePosition=eye_pos.tolist(),
                cameraTargetPosition=self.camera_target.tolist(),
                cameraUpVector=self.up_vector.tolist(),
                physicsClientId=self.client_id,
            )

            proj_matrix = p.computeProjectionMatrixFOV(
                fov=self.fov,
                aspect=self.aspect,
                nearVal=self.near_val,
                farVal=self.far_val,
                physicsClientId=self.client_id,
            )

            _, _, rgb, depth, _ = p.getCameraImage(
                width=self.width,
                height=self.height,
                viewMatrix=view_matrix,
                projectionMatrix=proj_matrix,
                shadow=shadow,
                renderer=p.ER_TINY_RENDERER,
                physicsClientId=self.client_id,
            )

            # PyBullet returns RGBA buffer
            rgb_array = np.array(rgb, dtype=np.uint8).reshape((self.height, self.width, 4))
            rgb_image = rgb_array[:, :, :3]  # Extract RGB channels

            # Linearize depth buffer
            depth_buffer = np.array(depth, dtype=np.float32).reshape((self.height, self.width))
            depth_image = self.far_val * self.near_val / (self.far_val - (self.far_val - self.near_val) * depth_buffer)
            return rgb_image, depth_image

        # High-performance analytical camera projection fallback
        rgb_image = np.full((self.height, self.width, 3), 40, dtype=np.uint8)
        # Add table plane background
        rgb_image[self.height // 3 :, :, 0] = 70
        rgb_image[self.height // 3 :, :, 1] = 65
        rgb_image[self.height // 3 :, :, 2] = 60

        # Project target sphere onto image plane
        t_pos = target_pos if target_pos is not None else np.array([0.0, 0.0, 0.2])
        tx = int(np.clip((t_pos[0] + 0.3) / 0.6 * self.width, 10, self.width - 10))
        ty = int(np.clip((0.5 - t_pos[2]) / 0.5 * self.height, 10, self.height - 10))
        
        # Render red target sphere
        y_grid, x_grid = np.ogrid[:self.height, :self.width]
        target_mask = ((x_grid - tx) ** 2 + (y_grid - ty) ** 2) <= (self.width // 14) ** 2
        rgb_image[target_mask] = [230, 40, 40]

        # Project end-effector onto image plane
        e_pos = ee_pos if ee_pos is not None else np.array([0.0, 0.0, 0.0])
        ex = int(np.clip((e_pos[0] + 0.3) / 0.6 * self.width, 5, self.width - 5))
        ey = int(np.clip((0.5 - e_pos[2]) / 0.5 * self.height, 5, self.height - 5))
        ee_mask = ((x_grid - ex) ** 2 + (y_grid - ey) ** 2) <= (self.width // 18) ** 2
        rgb_image[ee_mask] = [40, 160, 240]

        depth_image = np.full((self.height, self.width), 0.8, dtype=np.float32)
        return rgb_image, depth_image
