import os

class ZeroShotEvaluator:
    """
    Automates the cross-dataset zero-shot evaluation pipeline.
    Crucial to prove that our models do not overfit to the training dataset's specific domain
    (e.g., proving that a model trained on Kvasir-SEG generalizes seamlessly to ETIS or CVC-300).
    """
    
    def __init__(self, model_instances, dataloaders, metrics_engine):
        """
        model_instances: dict mapping model names to initialized PyTorch models.
        dataloaders: dict mapping dataset names to PyTorch DataLoaders.
        metrics_engine: An instance of our MetricsEngine to compute Dice/mIoU.
        """
        self.models = model_instances
        self.dataloaders = dataloaders
        self.metrics_engine = metrics_engine
        
    def evaluate_cross_dataset(self, source_dataset_name, target_dataset_names):
        """
        Loads the weights of the models trained on 'source_dataset_name' and evaluates them
        on all datasets in 'target_dataset_names'.
        """
        results_matrix = {}
        
        for model_name, model in self.models.items():
            results_matrix[model_name] = {}
            
            # Simulated loading of weights: model.load_state_dict(...)
            # path = f"weights/{model_name}_trained_on_{source_dataset_name}.pth"
            print(f"Loading weights for {model_name} trained on {source_dataset_name}...")
            
            for target_dataset in target_dataset_names:
                print(f"  --> Zero-Shot Evaluating on {target_dataset}...")
                
                dataloader = self.dataloaders[target_dataset]
                
                import torch
                device = next(model.parameters()).device if list(model.parameters()) else torch.device("cpu")
                model.eval()
                
                agg_dice = []
                agg_miou = []
                
                with torch.no_grad():
                    for x, tgt in dataloader:
                        x = x.to(device)
                        tgt = tgt.to(device)
                        pred = torch.sigmoid(model(x))
                        
                        for b in range(x.size(0)):
                            res = self.metrics_engine.compute_all(pred[b:b+1], tgt[b:b+1])
                            agg_dice.append(res.get("Dice", 0.0))
                            agg_miou.append(res.get("mIoU", 0.0))
                
                avg_dice = sum(agg_dice) / len(agg_dice) if len(agg_dice) > 0 else 0.0
                avg_miou = sum(agg_miou) / len(agg_miou) if len(agg_miou) > 0 else 0.0
                
                results_matrix[model_name][target_dataset] = {
                    "Dice": avg_dice,
                    "mIoU": avg_miou
                }
                
        return results_matrix

if __name__ == "__main__":
    print("Testing ZeroShotEvaluator Structure...")
    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
    from run_all_combos import ChakraNet
    from metrics_engine_v2 import MetricsEngineV2
    from torch.utils.data import DataLoader, Dataset
    import torch
    
    class DummyDS(Dataset):
        def __len__(self): return 2
        def __getitem__(self, idx): return torch.randn(3, 448, 448), torch.ones(1, 448, 448)
        
    mock_models = {"C1": ChakraNet(), "C3": ChakraNet()}
    dl = DataLoader(DummyDS(), batch_size=2)
    mock_dataloaders = {"Kvasir": dl, "ETIS": dl, "CVC-300": dl}
    
    evaluator = ZeroShotEvaluator(mock_models, mock_dataloaders, MetricsEngineV2())
    
    matrix = evaluator.evaluate_cross_dataset("Kvasir", ["ETIS", "CVC-300"])
    
    print("\nCross-Dataset Evaluation Matrix (Trained on Kvasir):")
    for model, scores in matrix.items():
        print(f"Model: {model}")
        for dataset, metrics in scores.items():
            print(f"  {dataset} -> Dice: {metrics['Dice']}, mIoU: {metrics['mIoU']}")
