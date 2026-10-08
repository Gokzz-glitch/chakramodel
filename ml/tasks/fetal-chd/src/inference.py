import os
import tarfile
import tempfile
from pathlib import Path
import torch
import torchvision.transforms as transforms
from PIL import Image
from models import ImageEncoder, TabularEncoder, MultimodalClassifier


class ModelLoader:
    """Load and manage pre-trained CHD models from archives."""
    
    def __init__(self, device='cpu'):
        self.device = device
    
    def extract_archive(self, archive_path):
        """Extract tar.gz archive to temporary directory."""
        with tarfile.open(archive_path, 'r:gz') as tar:
            temp_dir = tempfile.mkdtemp()
            tar.extractall(temp_dir)
        return temp_dir
    
    def load_image_encoder(self, archive_path, fold=0):
        """Load Vision Transformer image encoder from archive.
        
        Args:
            archive_path: Path to image_encoder.tar(CHd).gz
            fold: Fold index (0, 1, or 2)
        
        Returns:
            Loaded model on specified device
        """
        temp_dir = self.extract_archive(archive_path)
        model_path = Path(temp_dir) / 'img_script' / 'image_checkpoints' / 'image_encoder' / f'fold{fold}_best_model.pth'
        
        # Create model with correct architecture (384 embed, 6 heads, 12 depth)
        # Checkpoint has 1 output, but we need 2 for binary classification
        model = ImageEncoder(num_classes=1, embed_dim=384, depth=12, num_heads=6)
        checkpoint = torch.load(str(model_path), map_location=self.device)
        
        # Handle checkpoint without 'vit.' prefix
        if 'vit.cls_token' not in checkpoint and 'cls_token' in checkpoint:
            new_state_dict = {}
            for k, v in checkpoint.items():
                new_state_dict[f'vit.{k}'] = v
            checkpoint = new_state_dict
        
        model.load_state_dict(checkpoint, strict=True)
        model.to(self.device)
        model.eval()
        
        return model, temp_dir
    
    def load_tabular_encoder(self, archive_path, fold=0):
        """Load tabular transformer encoder from archive.
        
        Args:
            archive_path: Path to tabular_encoder.tar(chd).gz
            fold: Fold index (0, 1, or 2)
        
        Returns:
            Loaded model on specified device
        """
        temp_dir = self.extract_archive(archive_path)
        model_path = Path(temp_dir) / 'tabular_encoder' / f'fold{fold}_best_model.pth'
        
        # Create model matching checkpoint (input_dim=1, single output)
        # Checkpoint has 12416 -> 128 in linear layer, suggesting it flattens transformer output
        model = TabularEncoder(input_dim=1, embed_dim=128, num_heads=4, num_layers=2, num_classes=1, flatten=True)
        checkpoint = torch.load(str(model_path), map_location=self.device)
        
        model.load_state_dict(checkpoint, strict=False)
        model.to(self.device)
        model.eval()
        
        return model, temp_dir


class CHDPredictor:
    """Inference pipeline for CHD classification from ultrasound images."""
    
    def __init__(self, image_encoder_path, tabular_encoder_path, fold=0, device='cpu'):
        """Initialize predictor with model paths.
        
        Args:
            image_encoder_path: Path to image_encoder.tar(CHd).gz
            tabular_encoder_path: Path to tabular_encoder.tar(chd).gz
            fold: Cross-validation fold (0, 1, 2)
            device: 'cpu' or 'cuda'
        """
        self.device = device
        loader = ModelLoader(device=device)
        
        self.image_model, self.img_temp = loader.load_image_encoder(image_encoder_path, fold)
        self.tabular_model, self.tab_temp = loader.load_tabular_encoder(tabular_encoder_path, fold)
        
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def predict_from_image(self, image_path):
        """Predict CHD from single ultrasound image.
        
        Args:
            image_path: Path to image file
        
        Returns:
            dict: {'CHD': prob, 'Non_CHD': prob, 'prediction': 'CHD' or 'Non_CHD', 'confidence': score}
        """
        image = Image.open(image_path).convert('RGB')
        image_tensor = self.transform(image).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            output = self.image_model(image_tensor)
            # Model outputs single value (binary classification as regression or single class)
            # Assume: output > 0.5 means CHD, else Non_CHD
            if output.shape[-1] == 1:
                score = torch.sigmoid(output)[0, 0].item()
                chd_prob = score
                non_chd_prob = 1.0 - score
            else:
                probs = torch.softmax(output, dim=1)[0]
                chd_prob = probs[0].item()
                non_chd_prob = probs[1].item() if len(probs) > 1 else (1.0 - chd_prob)
        
        pred_label = 'CHD' if chd_prob > 0.5 else 'Non_CHD'
        confidence = max(chd_prob, non_chd_prob)
        
        return {
            'CHD': chd_prob,
            'Non_CHD': non_chd_prob,
            'prediction': pred_label,
            'confidence': confidence
        }
    
    def predict_from_batch(self, image_dir):
        """Batch predict from directory of images.
        
        Args:
            image_dir: Directory containing .png or .jpg images
        
        Returns:
            list: List of prediction dicts with image names
        """
        results = []
        image_dir = Path(image_dir)
        
        for img_file in sorted(image_dir.glob('*.png')) + sorted(image_dir.glob('*.jpg')):
            pred = self.predict_from_image(str(img_file))
            pred['image'] = img_file.name
            results.append(pred)
        
        return results
    
    def cleanup(self):
        """Clean up temporary directories."""
        import shutil
        shutil.rmtree(self.img_temp, ignore_errors=True)
        shutil.rmtree(self.tab_temp, ignore_errors=True)


if __name__ == '__main__':
    # Example usage
    img_archive = r'J:\My Drive\downloads\image_encoder.tar(CHd).gz'
    tab_archive = r'J:\My Drive\downloads\tabular_encoder.tar(chd).gz'
    dataset_path = r'I:\My Drive\heartbeat\CARDIUM_dataset\CHD'
    
    predictor = CHDPredictor(img_archive, tab_archive, fold=0, device='cpu')
    
    # Test single image
    sample_images = list(Path(dataset_path).rglob('*.png'))
    if sample_images:
        result = predictor.predict_from_image(str(sample_images[0]))
        print(f"Single image result: {result}")
        print(f"✓ Model loaded and inference working!")
    
    predictor.cleanup()
