import torch
import time
import psutil
import os
try:
    from thop import profile
    THOP_AVAILABLE = True
except ImportError:
    THOP_AVAILABLE = False

class CostProfiler:
    """
    Evaluates the computational cost of a PyTorch model:
    - Parameters (M)
    - FLOPs (G)
    - GPU Memory (MB)
    - Inference FPS
    """
    
    @staticmethod
    def profile_model(model, input_size=(1, 3, 256, 256), device="cuda"):
        """
        Profiles the model and returns a dictionary of cost metrics.
        """
        dummy_input = torch.randn(*input_size).to(device)
        model = model.to(device)
        model.eval()
        
        # 1. FLOPs and Params
        macs, params = 0, 0
        if THOP_AVAILABLE:
            macs, params = profile(model, inputs=(dummy_input,), verbose=False)
        else:
            params = sum(p.numel() for p in model.parameters() if p.requires_grad)
            print("thop library not installed, FLOPs set to 0. Use: pip install thop")
            
        # 2. Inference FPS (Averaged over 100 runs after 10 warmup runs)
        with torch.no_grad():
            for _ in range(10):
                _ = model(dummy_input)
                
            if device == "cuda":
                torch.cuda.synchronize()
            start_time = time.time()
            
            for _ in range(100):
                _ = model(dummy_input)
                
            if device == "cuda":
                torch.cuda.synchronize()
            end_time = time.time()
            
        fps = 100 / (end_time - start_time)
        
        # 3. Memory
        memory_mb = 0
        if device == "cuda":
            memory_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
        else:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 ** 2)
            
        return {
            "Params (M)": params / 1e6,
            "FLOPs (G)": (macs * 2) / 1e9 if THOP_AVAILABLE else 0, # Multiply by 2 for FLOPs instead of MACs
            "Inference FPS": fps,
            "Max Memory (MB)": memory_mb
        }

if __name__ == "__main__":
    # Test on a dummy ConvNet
    import torch.nn as nn
    class DummyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = nn.Conv2d(3, 64, 3, padding=1)
            self.conv2 = nn.Conv2d(64, 1, 3, padding=1)
        def forward(self, x):
            return self.conv2(F.relu(self.conv1(x)))
            
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Profiling on {device}...")
    profiler = CostProfiler()
    metrics = profiler.profile_model(DummyNet(), device=device)
    for k, v in metrics.items():
        print(f"{k}: {v:.2f}")
