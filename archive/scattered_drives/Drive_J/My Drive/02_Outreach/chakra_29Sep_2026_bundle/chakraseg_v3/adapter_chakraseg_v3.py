"""
Adapter so a ChakraSeg-v3 run can be scored by leakbench/audit_external_model.py.

Interface (same as leakbench/adapters/chakraguard.py):
    load(device)  -> returns predict
    predict(bgr)  -> HxW float32 probability map in [0, 1] at the input's resolution

Point it at a run directory with the CHAKRASEG_RUN environment variable, e.g.
    CHAKRASEG_RUN=/kaggle/working/runs_v3/R10a_s42 python audit_external_model.py \
        --adapter adapters/adapter_chakraseg_v3.py ...
The probability returned is the *gated* one (mask x presence) when the run has a presence head.
"""
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chakraseg_v3 as C  # noqa: E402

_state = {}


def load(device="cuda"):
    run = os.environ.get("CHAKRASEG_RUN")
    if not run:
        raise RuntimeError("set CHAKRASEG_RUN to a run directory (config.json + best.pt)")
    dev = torch.device(device if (device != "cuda" or torch.cuda.is_available()) else "cpu")
    model, a = C.load_run(run, dev)
    _state.update(model=model, a=a, device=dev)
    return predict


@torch.no_grad()
def predict(bgr):
    import cv2
    model, a, dev = _state["model"], _state["a"], _state["device"]
    H, W = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    x = cv2.resize(rgb, (a.img_size, a.img_size), interpolation=cv2.INTER_LINEAR)
    x = (x.astype(np.float32) / 255.0 - C.MEAN) / C.STD
    x = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(dev)
    with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=(dev.type == "cuda")):
        p, _, _ = C.predict_probs(model, x, use_presence=True, tta=bool(getattr(a, "tta", 0)),
                                  gate=getattr(a, "gate", "hard"), tau=getattr(a, "gate_tau", 0.5))
    p = F.interpolate(p.float(), size=(H, W), mode="bilinear", align_corners=False)[0, 0]
    return p.clamp(0, 1).cpu().numpy().astype(np.float32)
