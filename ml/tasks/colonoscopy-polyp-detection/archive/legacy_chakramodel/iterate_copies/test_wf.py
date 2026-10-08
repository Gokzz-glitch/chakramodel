import numpy as np
import torch
from scipy.ndimage import distance_transform_edt, convolve

def eval_wf_measure(predict, target, beta2=1.0):
    eps = 1e-5
    pred = predict.squeeze().cpu().numpy()
    gt = target.squeeze().cpu().numpy()
    
    if np.all(~(gt > 0)):
        return 0.0
        
    Dst, Idxt = distance_transform_edt(gt == 0, return_indices=True)
    E = np.abs(pred - gt)
    Et = np.copy(E)
    Et[gt == 0] = Et[Idxt[0][gt == 0], Idxt[1][gt == 0]]
    
    m, n = 3, 3 
    y, x = np.ogrid[-m : m + 1, -n : n + 1]
    h = np.exp(-(x * x + y * y) / (2 * 5 * 5))
    h[h < np.finfo(h.dtype).eps * h.max()] = 0
    sumh = h.sum()
    if sumh != 0:
        h /= sumh
        
    EA = convolve(Et, weights=h, mode="constant", cval=0)
    MIN_E_EA = np.where((gt == 1) & (EA < E), EA, E)
    
    B = np.where(gt == 0, 2 - np.exp(np.log(0.5) / 5 * Dst), np.ones_like(gt))
    Ew = MIN_E_EA * B
    
    TPw = np.sum(gt) - np.sum(Ew[gt == 1])
    FPw = np.sum(Ew[gt == 0])
    
    R = 1 - np.mean(Ew[gt == 1])
    P = TPw / (TPw + FPw + eps)
    
    Fbw = (1 + beta2) * R * P / (R + beta2 * P + eps)
    print(f"R: {R}, P: {P}, TPw: {TPw}, FPw: {FPw}, sum(gt): {np.sum(gt)}")
    return float(Fbw)

# Test with 0/255 instead of 0/1!
# evaluate_all.py uses c_bin = (c_mask_orig > 127).astype(np.uint8). This is 0/1!
# Wait, NO!
# ablation_study.py does: c_bin = (c_mask > 127).astype(np.uint8). That's 0/1.
# BUT what if evaluate_all.py passed 0/255?
gt = torch.zeros((1, 100, 100))
gt[0, 20:80, 20:80] = 1

pred = torch.zeros((1, 100, 100))
pred[0, 25:75, 25:75] = 1

print("Normal 0/1 case:", eval_wf_measure(pred, gt))

gt_255 = gt * 255
pred_255 = pred * 255
print("0/255 case:", eval_wf_measure(pred_255, gt_255))
