import torch
import torchvision
import torchvision.transforms as transforms
import os

def get_dataloader(batch_size=64, download_dir='./data'):
    """
    Downloads the CIFAR-10 dataset (clean, not web-scraped) and returns a PyTorch DataLoader.
    CIFAR-10 images are 32x32 RGB.
    """
    os.makedirs(download_dir, exist_ok=True)
    
    transform = transforms.Compose([
        transforms.ToTensor(),
        # Normalize to [-1, 1] for GAN training
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])

    print("Downloading/Loading CIFAR-10 Dataset...")
    trainset = torchvision.datasets.CIFAR10(root=download_dir, train=True,
                                            download=True, transform=transform)
    
    trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size,
                                              shuffle=True, num_workers=2, drop_last=True)
    
    return trainloader

if __name__ == "__main__":
    loader = get_dataloader()
    dataiter = iter(loader)
    images, labels = next(dataiter)
    print(f"Successfully loaded a batch of {images.size(0)} images with shape {images.shape}.")
