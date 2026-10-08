from collections import deque

import torch


class TemporalPresenceGate:
    """Require persistent frame evidence before reporting a detection.

    The gate operates on a frame-level foreground fraction and returns whether
    the current video stream should be considered positive. It deliberately
    does not alter segmentation logits or masks.
    """

    def __init__(
        self,
        on_fraction=0.001,
        off_fraction=0.0005,
        on_frames=3,
        off_frames=5,
    ):
        if on_fraction < 0 or off_fraction < 0:
            raise ValueError("Foreground thresholds must be non-negative")
        if off_fraction > on_fraction:
            raise ValueError("off_fraction cannot exceed on_fraction")
        if on_frames < 1 or off_frames < 1:
            raise ValueError("Frame persistence must be at least one")
        self.on_fraction = float(on_fraction)
        self.off_fraction = float(off_fraction)
        self.on_frames = int(on_frames)
        self.off_frames = int(off_frames)
        self.reset()

    def reset(self):
        self.active = False
        self._on_history = deque(maxlen=self.on_frames)
        self._off_history = deque(maxlen=self.off_frames)

    @staticmethod
    def foreground_fraction(mask_or_probability, threshold=0.5):
        if not isinstance(mask_or_probability, torch.Tensor):
            raise TypeError("mask_or_probability must be a torch.Tensor")
        if mask_or_probability.ndim not in (2, 3, 4):
            raise ValueError("Expected [H,W], [B,H,W], or [B,1,H,W] tensor")
        values = mask_or_probability
        if values.ndim == 4:
            if values.shape[1] != 1:
                raise ValueError("Expected a single-channel mask or probability map")
            values = values[:, 0]
        if values.dtype.is_floating_point:
            values = values >= threshold
        return float(values.to(dtype=torch.float32).mean().item())

    def update(self, mask_or_probability, threshold=0.5):
        """Update state and return ``(is_active, foreground_fraction)``."""
        fraction = self.foreground_fraction(mask_or_probability, threshold)
        if self.active:
            self._off_history.append(fraction <= self.off_fraction)
            self._on_history.clear()
            if len(self._off_history) == self.off_frames and all(self._off_history):
                self.active = False
                self._off_history.clear()
        else:
            self._on_history.append(fraction >= self.on_fraction)
            self._off_history.clear()
            if len(self._on_history) == self.on_frames and all(self._on_history):
                self.active = True
                self._on_history.clear()
        return self.active, fraction
