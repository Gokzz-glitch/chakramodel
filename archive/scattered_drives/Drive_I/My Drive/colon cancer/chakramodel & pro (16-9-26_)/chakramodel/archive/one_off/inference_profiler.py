import torch
import time
from thop import profile
from thop import clever_format

class InferenceProfiler:
    """
    Profiles inference efficiency: FPS, MACs, FLOPs, and Parameter Count.
    Essential to prove the clinical deployment viability of C1 (EfficientNet+UNet) on edge devices.
    """
    
    @staticmethod
    def profile_model(model, input_size=(1, 3, 256, 256), device="cpu", iterations=100):
        """
        Profiles a PyTorch model for efficiency.
        model: PyTorch nn.Module
        input_size: Tuple representing input tensor shape
        """
        model = model.to(device)
        model.eval()
        dummy_input = torch.randn(input_size).to(device)
        
        # 1. Warm-up
        with torch.no_grad():
            for _ in range(10):
                _ = model(dummy_input)
                
        # 2. FPS Calculation
        start_time = time.time()
        with torch.no_grad():
            for _ in range(iterations):
                _ = model(dummy_input)
        
        # Use torch.cuda.synchronize() if on GPU to get accurate timing
        if device == "cuda":
            torch.cuda.synchronize()
            
        end_time = time.time()
        total_time = end_time - start_time
        fps = iterations / total_time
        
        # 3. MACs/FLOPs and Params using THOP
        macs, params = profile(model, inputs=(dummy_input, ), verbose=False)
        macs_formatted, params_formatted = clever_format([macs, params], "%.3f")
        flops = macs * 2 # Standard approximation (1 MAC = 2 FLOPs)
        _, flops_formatted = clever_format([macs, flops], "%.3f")
        
        print(f"--- Profiling Results ({device.upper()}) ---")
        print(f"Parameters: {params_formatted}")
        print(f"MACs:       {macs_formatted}")
        print(f"FLOPs:      {flops_formatted}")
        print(f"FPS:        {fps:.2f} frames/sec (Batch Size {input_size[0]})")
        
        return {
            "params": params,
            "macs": macs,
            "flops": flops,
            "fps": fps
        }

if __name__ == "__main__":
    import torchvision.models as models
    # Quick Test with ResNet18 as a proxy
    print("Testing InferenceProfiler with ResNet18...")
    dummy_model = models.resnet18()
    InferenceProfiler.profile_model(dummy_model)
