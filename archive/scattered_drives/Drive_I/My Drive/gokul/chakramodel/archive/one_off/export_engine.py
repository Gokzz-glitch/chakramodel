from ultralytics import YOLO
import sys

def main():
    print("[INFO] Loading ChakraModel weights...")
    model = YOLO("weights/best.pt")
    
    print("[INFO] Attempting to export to TensorRT engine (FP16)...")
    try:
        # Export to TensorRT Engine
        # This will optimize the CUDA kernels for the specific GPU architecture
        model.export(
            format="engine",
            half=True,       # Use FP16 half precision for TensorCores
            device=0,        # Export on GPU 0
            workspace=2      # Allocate 2GB VRAM workspace for optimization
        )
        print("[SUCCESS] Exported TensorRT .engine model!")
    except Exception as e:
        print(f"[ERROR] TensorRT export failed: {e}")
        print("[INFO] Make sure NVIDIA TensorRT libraries are installed (pip install tensorrt).")
        
        print("\n[INFO] Falling back to ONNX (GPU) export...")
        try:
            model.export(
                format="onnx",
                half=True,
                device=0,
                simplify=True
            )
            print("[SUCCESS] Exported ONNX FP16 model!")
        except Exception as e2:
            print(f"[ERROR] ONNX export failed: {e2}")

if __name__ == "__main__":
    main()
