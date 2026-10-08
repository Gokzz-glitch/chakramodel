"""Evaluation metrics and visualization for CHD predictions."""
import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, precision_recall_curve, auc, confusion_matrix
)
import seaborn as sns


class CHDEvaluator:
    """Comprehensive evaluation for CHD classification."""
    
    def __init__(self, device='cpu'):
        self.device = device
        self.reset()
    
    def reset(self):
        """Reset predictions and labels."""
        self.all_preds = []
        self.all_labels = []
        self.all_probs = []
        self.all_image_paths = []
    
    def add_batch(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        image_paths: List[str] = None
    ):
        """Add batch predictions.
        
        Args:
            logits: Model outputs (batch_size, 2)
            labels: Ground truth labels (batch_size,)
            image_paths: Optional image paths for error analysis
        """
        probs = torch.softmax(logits, dim=1)
        preds = probs.argmax(dim=1)
        
        self.all_probs.extend(probs[:, 1].detach().cpu().numpy())
        self.all_preds.extend(preds.detach().cpu().numpy())
        self.all_labels.extend(labels.detach().cpu().numpy())
        
        if image_paths is not None:
            self.all_image_paths.extend(image_paths)
    
    def compute_metrics(self) -> Dict:
        """Compute classification metrics.
        
        Returns:
            Dictionary with metrics
        """
        preds = np.array(self.all_preds)
        labels = np.array(self.all_labels)
        probs = np.array(self.all_probs)
        
        metrics = {
            'accuracy': accuracy_score(labels, preds),
            'precision': precision_score(labels, preds, zero_division=0),
            'recall': recall_score(labels, preds, zero_division=0),
            'f1': f1_score(labels, preds, zero_division=0),
            'roc_auc': roc_auc_score(labels, probs),
        }
        
        # Per-class metrics
        for class_idx, class_name in enumerate(['Non_CHD', 'CHD']):
            binary_labels = (labels == class_idx).astype(int)
            binary_preds = (preds == class_idx).astype(int)
            
            metrics[f'{class_name}_precision'] = precision_score(binary_labels, binary_preds, zero_division=0)
            metrics[f'{class_name}_recall'] = recall_score(binary_labels, binary_preds, zero_division=0)
            metrics[f'{class_name}_f1'] = f1_score(binary_labels, binary_preds, zero_division=0)
        
        return metrics
    
    def plot_confusion_matrix(self, save_path: str = None):
        """Plot confusion matrix.
        
        Args:
            save_path: Path to save figure (optional)
        """
        cm = confusion_matrix(self.all_labels, self.all_preds)
        
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Non_CHD', 'CHD'],
            yticklabels=['Non_CHD', 'CHD']
        )
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.title('Confusion Matrix - CHD Classification')
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved: {save_path}")
        else:
            plt.show()
        
        plt.close()
    
    def plot_roc_curve(self, save_path: str = None):
        """Plot ROC curve.
        
        Args:
            save_path: Path to save figure (optional)
        """
        fpr, tpr, _ = roc_curve(self.all_labels, self.all_probs)
        roc_auc = auc(fpr, tpr)
        
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random Classifier')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve - CHD Detection')
        plt.legend(loc="lower right")
        plt.grid(alpha=0.3)
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved: {save_path}")
        else:
            plt.show()
        
        plt.close()
    
    def plot_pr_curve(self, save_path: str = None):
        """Plot Precision-Recall curve.
        
        Args:
            save_path: Path to save figure (optional)
        """
        precision, recall, _ = precision_recall_curve(self.all_labels, self.all_probs)
        pr_auc = auc(recall, precision)
        
        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, color='blue', lw=2, label=f'PR curve (AUC = {pr_auc:.3f})')
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve - CHD Detection')
        plt.legend(loc="best")
        plt.grid(alpha=0.3)
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved: {save_path}")
        else:
            plt.show()
        
        plt.close()
    
    def plot_metrics_summary(self, save_path: str = None):
        """Plot metrics summary bar chart.
        
        Args:
            save_path: Path to save figure (optional)
        """
        metrics = self.compute_metrics()
        
        metric_names = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']
        metric_values = [metrics[k] for k in metric_names]
        
        plt.figure(figsize=(10, 6))
        bars = plt.bar(metric_names, metric_values, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
        
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom')
        
        plt.ylabel('Score')
        plt.title('CHD Classification Metrics Summary')
        plt.ylim([0, 1.1])
        plt.grid(axis='y', alpha=0.3)
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Saved: {save_path}")
        else:
            plt.show()
        
        plt.close()
    
    def print_report(self):
        """Print comprehensive evaluation report."""
        metrics = self.compute_metrics()
        
        print("\n" + "="*60)
        print("CHD CLASSIFICATION EVALUATION REPORT")
        print("="*60)
        print(f"\nDataset Size: {len(self.all_labels)}")
        print(f"  CHD cases: {sum(self.all_labels)}")
        print(f"  Non-CHD cases: {len(self.all_labels) - sum(self.all_labels)}")
        
        print("\n" + "-"*60)
        print("OVERALL METRICS")
        print("-"*60)
        for key in ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']:
            print(f"  {key.upper():<12} {metrics[key]:>8.4f}")
        
        print("\n" + "-"*60)
        print("PER-CLASS METRICS")
        print("-"*60)
        for class_name in ['Non_CHD', 'CHD']:
            print(f"\n{class_name}:")
            for suffix in ['_precision', '_recall', '_f1']:
                key = class_name + suffix
                print(f"  {suffix[1:].upper():<12} {metrics[key]:>8.4f}")
        
        print("\n" + "="*60 + "\n")
    
    def get_misclassified(self) -> List[Dict]:
        """Get list of misclassified samples.
        
        Returns:
            List of dicts with prediction info for errors
        """
        errors = []
        for i, (pred, label, prob) in enumerate(zip(self.all_preds, self.all_labels, self.all_probs)):
            if pred != label:
                error_info = {
                    'index': i,
                    'true_label': label,
                    'pred_label': pred,
                    'confidence': prob,
                    'image_path': self.all_image_paths[i] if self.all_image_paths else None
                }
                errors.append(error_info)
        
        return sorted(errors, key=lambda x: abs(x['confidence'] - 0.5))


def evaluate_model(model, val_loader, device='cpu', output_dir='./evaluation'):
    """Complete evaluation pipeline.
    
    Args:
        model: Model to evaluate
        val_loader: Validation data loader
        device: Device to use
        output_dir: Directory for output figures
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    model.eval()
    evaluator = CHDEvaluator(device=device)
    
    print("Running inference on validation set...")
    with torch.no_grad():
        for images, labels, paths in val_loader:
            images = images.to(device)
            labels = labels.to(device)
            
            logits = model(images)
            evaluator.add_batch(logits, labels, paths)
    
    print("\nGenerating evaluation report...")
    evaluator.print_report()
    
    print("Saving figures...")
    evaluator.plot_confusion_matrix(os.path.join(output_dir, 'confusion_matrix.png'))
    evaluator.plot_roc_curve(os.path.join(output_dir, 'roc_curve.png'))
    evaluator.plot_pr_curve(os.path.join(output_dir, 'pr_curve.png'))
    evaluator.plot_metrics_summary(os.path.join(output_dir, 'metrics_summary.png'))
    
    return evaluator


if __name__ == '__main__':
    from data import CARDIUMDataModule
    from models import ImageEncoder
    
    # Example usage
    data = CARDIUMDataModule(r'I:\My Drive\heartbeat', fold=1, batch_size=32)
    model = ImageEncoder(num_classes=2)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    evaluate_model(model, data.val_loader(), device=device, output_dir='./evaluation')
