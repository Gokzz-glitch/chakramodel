import cv2
import numpy as np
import random
from pathlib import Path
import albumentations as A
from albumentations.pytorch import ToTensorV2

class CopyPasteAugmentation:
    """
    Copy-Paste Augmentation for Polyp Segmentation.
    Synthesizes camouflaged polyps by taking a polyp from a donor image and pasting it onto the target.
    """
    def __init__(self, data_root, manifest_data, p=0.3):
        self.data_root = Path(data_root)
        self.manifest_data = manifest_data
        self.p = p

    def _get_random_donor(self):
        idx = random.randint(0, len(self.manifest_data) - 1)
        row = self.manifest_data.iloc[idx]
        img_path = self.data_root / row['image']
        mask_path = self.data_root / row['mask']
        
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        return image, mask

    def __call__(self, image, mask):
        if random.random() > self.p:
            return image, mask
            
        donor_img, donor_mask = self._get_random_donor()
        
        # Extract polyp from donor
        contours, _ = cv2.findContours(donor_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image, mask
            
        # Select random contour
        contour = random.choice(contours)
        x, y, w, h = cv2.boundingRect(contour)
        
        if w == 0 or h == 0:
            return image, mask
            
        polyp_img = donor_img[y:y+h, x:x+w].copy()
        polyp_mask = donor_mask[y:y+h, x:x+w].copy()
        
        # Apply random affine transform
        scale = random.uniform(0.5, 1.5)
        angle = random.uniform(0, 360)
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, scale)
        
        # Calculate new bounding box after rotation
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        
        polyp_img = cv2.warpAffine(polyp_img, M, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        polyp_mask = cv2.warpAffine(polyp_mask, M, (new_w, new_h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        
        # Apply random flips
        if random.random() > 0.5:
            polyp_img = cv2.flip(polyp_img, 1)
            polyp_mask = cv2.flip(polyp_mask, 1)
        if random.random() > 0.5:
            polyp_img = cv2.flip(polyp_img, 0)
            polyp_mask = cv2.flip(polyp_mask, 0)
        
        # Find valid placement
        img_h, img_w = image.shape[:2]
        if new_w >= img_w or new_h >= img_h:
            return image, mask
            
        paste_x = random.randint(0, img_w - new_w)
        paste_y = random.randint(0, img_h - new_h)
        
        # Prepare seamless clone
        center_x = paste_x + new_w // 2
        center_y = paste_y + new_h // 2
        
        # Make sure center is within bounds
        center_x = max(new_w // 2, min(img_w - new_w // 2 - 1, center_x))
        center_y = max(new_h // 2, min(img_h - new_h // 2 - 1, center_y))
        
        result_img = image.copy()
        result_mask = mask.copy()
        
        try:
            # Mask needs to be 255 in the center of the object
            blend_mask = polyp_mask.copy()
            # Ensure mask is large enough
            result_img = cv2.seamlessClone(polyp_img, result_img, blend_mask, (center_x, center_y), cv2.NORMAL_CLONE)
        except Exception:
            # Fallback to direct paste
            roi_img = result_img[paste_y:paste_y+new_h, paste_x:paste_x+new_w]
            mask_bool = polyp_mask > 0
            roi_img[mask_bool] = polyp_img[mask_bool]
            result_img[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = roi_img
            
        # Update mask
        roi_mask = result_mask[paste_y:paste_y+new_h, paste_x:paste_x+new_w]
        mask_bool = polyp_mask > 0
        roi_mask[mask_bool] = 255
        result_mask[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = roi_mask
        
        return result_img, result_mask


class ColorExchangeAugmentation:
    """
    Randomly swaps R, G, B channels between the current image and a donor image.
    """
    def __init__(self, data_root, manifest_data, p=0.3):
        self.data_root = Path(data_root)
        self.manifest_data = manifest_data
        self.p = p
        
    def _get_random_donor(self, target_shape):
        idx = random.randint(0, len(self.manifest_data) - 1)
        row = self.manifest_data.iloc[idx]
        img_path = self.data_root / row['image']
        
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (target_shape[1], target_shape[0]))
        return image

    def __call__(self, image, mask):
        if random.random() > self.p:
            return image, mask
            
        donor_img = self._get_random_donor(image.shape)
        result_img = image.copy()
        
        # Randomly choose channels to swap
        channels_to_swap = random.sample([0, 1, 2], random.randint(1, 2))
        for c in channels_to_swap:
            result_img[:, :, c] = donor_img[:, :, c]
            
        return result_img, mask


class CutMixAugmentation:
    """
    CutMix augmentation combining two images and their masks.
    """
    def __init__(self, data_root, manifest_data, p=0.2, alpha=1.0):
        self.data_root = Path(data_root)
        self.manifest_data = manifest_data
        self.p = p
        self.alpha = alpha
        
    def _get_random_donor(self, target_shape):
        idx = random.randint(0, len(self.manifest_data) - 1)
        row = self.manifest_data.iloc[idx]
        img_path = self.data_root / row['image']
        mask_path = self.data_root / row['mask']
        
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        image = cv2.resize(image, (target_shape[1], target_shape[0]))
        mask = cv2.resize(mask, (target_shape[1], target_shape[0]), interpolation=cv2.INTER_NEAREST)
        return image, mask

    def __call__(self, image, mask):
        if random.random() > self.p:
            return image, mask
            
        donor_img, donor_mask = self._get_random_donor(image.shape)
        
        lam = np.random.beta(self.alpha, self.alpha)
        h, w = image.shape[:2]
        
        cut_rat = np.sqrt(1. - lam)
        cut_w = int(w * cut_rat)
        cut_h = int(h * cut_rat)
        
        cx = np.random.randint(w)
        cy = np.random.randint(h)
        
        bbx1 = np.clip(cx - cut_w // 2, 0, w)
        bby1 = np.clip(cy - cut_h // 2, 0, h)
        bbx2 = np.clip(cx + cut_w // 2, 0, w)
        bby2 = np.clip(cy + cut_h // 2, 0, h)
        
        result_img = image.copy()
        result_mask = mask.copy()
        
        result_img[bby1:bby2, bbx1:bbx2, :] = donor_img[bby1:bby2, bbx1:bbx2, :]
        result_mask[bby1:bby2, bbx1:bbx2] = donor_mask[bby1:bby2, bbx1:bbx2]
        
        return result_img, result_mask


def build_train_transforms(config):
    """
    Builds the standard albumentations pipeline for training.
    """
    img_size = config.get('img_size', 352)
    return A.Compose([
        A.Resize(img_size, img_size),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.2, rotate_limit=15, p=0.5, border_mode=cv2.BORDER_REFLECT_101),
        A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.5),
        A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ToTensorV2()
    ])

def build_val_transforms(config):
    """
    Builds the standard albumentations pipeline for validation.
    """
    img_size = config.get('img_size', 352)
    return A.Compose([
        A.Resize(img_size, img_size),
        A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ToTensorV2()
    ])
