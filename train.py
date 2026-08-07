from ultralytics import YOLO

def main():
    print("Initializing YOLO for ChakraModel Training on Local GPU...")
    
    # Load a pretrained model (YOLOv8n is chosen for laptop GPU compatibility and speed)
    model = YOLO('yolov8n.pt') 
    
    # Train the model
    # We use batch=8 or 16 depending on standard laptop VRAM (typically 4GB-8GB).
    results = model.train(
        data=r'M:\GOKZZ_4\NIT HACKATHIN\datasets\yolo\dataset.yaml',
        epochs=10, # Keep it low for the first run to ensure it works
        imgsz=640,
        batch=4,
        device=0, # Use GPU 0
        project='ChakraModel_Runs',
        name='polyp_detection_v1',
        augment=True,
        # Emulate artifacts using augmentations
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        shear=2.0,
        perspective=0.0,
        flipud=0.5,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.2
    )
    
    print("Training complete! Model saved to ChakraModel_Runs/polyp_detection_v1/weights/best.pt")

if __name__ == '__main__':
    main()
