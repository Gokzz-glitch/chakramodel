from ultralytics import YOLO

def main():
    print("Initializing Multi-Class YOLO for ChakraModel Training...")
    
    model = YOLO('yolov8n.pt') 
    
    # Train the model with 5 classes
    results = model.train(
        data=r'M:\GOKZZ_4\NIT HACKATHIN\datasets\yolo_multiclass\dataset_multiclass.yaml',
        epochs=50, 
        imgsz=640,
        batch=16, # Increased to saturate the 4GB VRAM
        workers=8, # Feed the GPU faster (CPU is at 26%)
        device=0, 
        project='ChakraModel_Runs',
        name='multiclass_detection_v1',
        augment=True,
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
    
    print("Multi-class Training complete! Model saved to ChakraModel_Runs/multiclass_detection_v1/weights/best.pt")

if __name__ == '__main__':
    main()
