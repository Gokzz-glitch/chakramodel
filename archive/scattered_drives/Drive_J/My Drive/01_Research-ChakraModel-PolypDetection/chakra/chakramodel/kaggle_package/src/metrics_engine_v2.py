import torch
import torch.nn.functional as F
import numpy as np
from scipy.ndimage import distance_transform_edt, convolve
import math

class MetricsEngineV2:
    """
    Rigorous evaluation metrics for Polyp Segmentation based on MICCAI standards.
    Contains Dice, mIoU, MAE, S-measure, E-measure, and wF-measure.
    """
    
    @staticmethod
    def eval_dice_iou(predict, target):
        """
        Computes Dice and IoU.
        predict: (H, W) or (B, 1, H, W) binary or prob map in [0,1]
        target: (H, W) or (B, 1, H, W) binary map {0,1}
        """
        pred = (predict > 0.5).float()
        tgt = target.float()
        
        intersection = (pred * tgt).sum()
        union = pred.sum() + tgt.sum() - intersection
        
        dice = (2. * intersection + 1e-5) / (pred.sum() + tgt.sum() + 1e-5)
        iou = (intersection + 1e-5) / (union + 1e-5)
        
        return dice.item(), iou.item()

    @staticmethod
    def eval_mae(predict, target):
        """
        Computes Mean Absolute Error (MAE).
        """
        return torch.abs(predict - target.float()).mean().item()
        
    @staticmethod
    def eval_wf_measure(predict, target, beta2=1.0):
        """
        Weighted F-measure (Fbw) by Margolin et al. 2014.
        """
        eps = 1e-5
        pred = predict.squeeze().float().cpu().numpy().astype(np.float32)
        gt = target.squeeze().float().cpu().numpy().astype(np.float32)
        
        if np.all(~(gt > 0)):
            return float(1.0 - np.mean(pred))
            
        Dst, Idxt = distance_transform_edt(gt == 0, return_indices=True)
        E = np.abs(pred - gt)
        Et = np.copy(E)
        Et[gt == 0] = Et[Idxt[0][gt == 0], Idxt[1][gt == 0]]
        
        m, n = 3, 3 # (7-1)/2
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
        return float(Fbw)
        
    @staticmethod
    def eval_s_measure(predict, target, alpha=0.5):
        """
        Structure-measure (S-measure) by Fan et al. 2017.
        Approximated via object and region aware SSIM components.
        """
        pred = predict.squeeze().float().cpu().numpy().astype(np.float32)
        gt = target.squeeze().float().cpu().numpy().astype(np.float32)
        
        y = np.mean(gt)
        if y == 0.0:  # bg
            return float(1.0 - np.mean(pred))
        if y == 1.0:  # fg
            return float(np.mean(pred))
            
        def ssim(p, g):
            if p.size == 0:
                return 1.0
            if p.shape[0] < 11 or p.shape[1] < 11:
                # fallback for tiny regions
                N = p.size
                x_m = np.mean(p)
                y_m = np.mean(g)
                sigma_x = np.sum((p - x_m) ** 2) / (N - 1 + 1e-5)
                sigma_y = np.sum((g - y_m) ** 2) / (N - 1 + 1e-5)
                sigma_xy = np.sum((p - x_m) * (g - y_m)) / (N - 1 + 1e-5)
                alpha_ = 4 * x_m * y_m * sigma_xy
                beta_ = (x_m**2 + y_m**2) * (sigma_x + sigma_y)
                if alpha_ != 0: return alpha_ / (beta_ + 1e-5)
                elif alpha_ == 0 and beta_ == 0: return 1.0
                return 0.0

            from scipy.ndimage import uniform_filter
            window_size = 11
            
            x_m = uniform_filter(p, window_size, mode='reflect')
            y_m = uniform_filter(g, window_size, mode='reflect')
            
            x_m_sq = x_m ** 2
            y_m_sq = y_m ** 2
            xy_m = x_m * y_m
            
            sigma_x = uniform_filter(p ** 2, window_size, mode='reflect') - x_m_sq
            sigma_y = uniform_filter(g ** 2, window_size, mode='reflect') - y_m_sq
            sigma_xy = uniform_filter(p * g, window_size, mode='reflect') - xy_m
            
            alpha_ = 4 * xy_m * sigma_xy
            beta_ = (x_m_sq + y_m_sq) * (sigma_x + sigma_y)
            
            ssim_map = np.zeros_like(alpha_)
            idx = beta_ != 0
            ssim_map[idx] = alpha_[idx] / (beta_[idx] + 1e-5)
            ssim_map[(alpha_ == 0) & (beta_ == 0)] = 1.0
            
            return float(np.mean(ssim_map))
            
        def s_object(x):
            mean = np.mean(x)
            std_x = np.std(x, ddof=1) if x.size > 1 else 0
            return 2 * mean / (mean**2 + 1 + std_x + 1e-5)
            
        gt_mean = np.mean(gt)
        fg_score = s_object(pred[gt == 1]) * gt_mean
        bg_score = s_object((1 - pred)[gt == 0]) * (1 - gt_mean)
        s_obj = fg_score + bg_score
        
        h, w = gt.shape
        cy, cx = np.argwhere(gt).mean(axis=0).round()
        cy = max(min(int(cy) + 1, h - 1), 1)
        cx = max(min(int(cx) + 1, w - 1), 1)
        # Prevent out-of-bounds NaN collapse for polyps on the extreme border
        cy = max(1, min(cy, h - 1))
        cx = max(1, min(cx, w - 1))
        
        w_lt = cx * cy / (h * w)
        w_rt = cy * (w - cx) / (h * w)
        w_lb = (h - cy) * cx / (h * w)
        w_rb = 1 - w_lt - w_rt - w_lb
        
        s_reg = (ssim(pred[0:cy, 0:cx], gt[0:cy, 0:cx]) * w_lt +
                 ssim(pred[0:cy, cx:w], gt[0:cy, cx:w]) * w_rt +
                 ssim(pred[cy:h, 0:cx], gt[cy:h, 0:cx]) * w_lb +
                 ssim(pred[cy:h, cx:w], gt[cy:h, cx:w]) * w_rb)
                 
        return float(alpha * s_obj + (1 - alpha) * s_reg)

    @staticmethod
    def eval_e_measure(predict, target):
        """
        Enhanced-alignment measure (E-measure) by Fan et al. 2018.
        """
        pred = predict.squeeze().float().cpu().numpy()
        gt = target.squeeze().float().cpu().numpy()
        
        if np.all(~(gt > 0)):
            return 1.0 - np.mean(pred)
        if np.all(gt > 0):
            return np.mean(pred)
            
        mean_pred_value = np.mean(pred)
        mean_gt_value = np.mean(gt)
        
        phi_fm = pred - mean_pred_value
        phi_gt = gt - mean_gt_value
        
        align_matrix = 2 * (phi_fm * phi_gt) / (phi_fm**2 + phi_gt**2 + 1e-5)
        enhanced_matrix = (align_matrix + 1)**2 / 4
        
        return float(np.sum(enhanced_matrix) / (gt.size - 1 + 1e-5))

    @classmethod
    def compute_all(cls, predict, target):
        """
        predict: (B, 1, H, W) logits/probs
        target: (B, 1, H, W) binary
        """
        if isinstance(predict, np.ndarray):
            predict = torch.from_numpy(predict)
        if isinstance(target, np.ndarray):
            target = torch.from_numpy(target)
            
        dice, iou = cls.eval_dice_iou(predict, target)
        mae = cls.eval_mae(predict, target)
        wfb = cls.eval_wf_measure(predict, target)
        sm = cls.eval_s_measure(predict, target)
        em = cls.eval_e_measure(predict, target)
        
        return {
            "Dice": dice,
            "mIoU": iou,
            "wF-measure": wfb,
            "S-measure": sm,
            "E-measure": em,
            "MAE": mae
        }

if __name__ == "__main__":
    pred = torch.rand(1, 1, 256, 256)
    tgt = (torch.rand(1, 1, 256, 256) > 0.5).float()
    metrics = MetricsEngineV2.compute_all(pred, tgt)
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")
