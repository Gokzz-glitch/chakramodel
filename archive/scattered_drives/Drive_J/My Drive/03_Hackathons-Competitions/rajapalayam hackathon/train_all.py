import os
import torch
from data_loader import get_dataloaders, CulturalObjectDataset
from gan_augmenter import train_gan
from cnn_detector import train_detector, CNNDetector
from torch.utils.data import DataLoader, ConcatDataset, TensorDataset

def run_overnight_training():
    print("=============================================")
    print("   DATA GENESIS 2026 - OVERNIGHT TRAINING    ")
    print("=============================================")
    
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Executing on device: {device}")
    
    os.makedirs('weights', exist_ok=True)
    
    print("\n--- [Phase 1] Initializing Data ---")
    train_loader, val_loader, _ = get_dataloaders('./data', batch_size=16)
    
    print("\n--- [Phase 2] Training Agent 1: DataGuard (GAN) ---")
    # Train for 500 epochs overnight
    generator, discriminator = train_gan(train_loader, num_epochs=500, device=device)
    torch.save(generator.state_dict(), 'weights/generator.pth')
    torch.save(discriminator.state_dict(), 'weights/discriminator.pth')
    
    print("\n--- [Phase 3] Generating Synthetic Dataset ---")
    generator.eval()
    augmented_imgs = []
    augmented_labels = []
    augmented_bboxes = []
    
    # Generate 1000 synthetic images
    with torch.no_grad():
        for _ in range(1000 // 16 + 1):
            noise = torch.randn(16, 100, 1, 1, device=device)
            fake_imgs = generator(noise).cpu()
            augmented_imgs.append(fake_imgs)
            # Assign random classes and center bboxes for the mock augmented data
            labels = torch.randint(0, 3, (16,))
            bboxes = torch.tensor([[0.5, 0.5, 0.4, 0.4]] * 16)
            augmented_labels.append(labels)
            augmented_bboxes.append(bboxes)
            
    aug_dataset = TensorDataset(torch.cat(augmented_imgs), torch.cat(augmented_labels), torch.cat(augmented_bboxes))
    
    # Combine real (mock) and synthetic
    combined_dataset = ConcatDataset([train_loader.dataset, aug_dataset])
    combined_loader = DataLoader(combined_dataset, batch_size=16, shuffle=True)
    print(f"Combined Dataset Size: {len(combined_dataset)}")
    
    print("\n--- [Phase 4] Training Agent 2: CNN Detector ---")
    # Train CNN for 200 epochs on the combined dataset
    detector = train_detector(combined_loader, num_epochs=200, device=device)
    torch.save(detector.state_dict(), 'weights/detector.pth')
    
    print("\n=============================================")
    print("   OVERNIGHT TRAINING COMPLETE! WEIGHTS SAVED  ")
    print("=============================================")

if __name__ == "__main__":
    run_overnight_training()
