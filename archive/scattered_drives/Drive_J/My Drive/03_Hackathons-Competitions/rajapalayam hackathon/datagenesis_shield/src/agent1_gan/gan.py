import torch
import torch.nn as nn
import os
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from torchvision.utils import save_image

class Generator(nn.Module):
    def __init__(self, latent_dim):
        super(Generator, self).__init__()
        self.init_size = 64 // 4
        self.l1 = nn.Sequential(nn.Linear(latent_dim, 128 * self.init_size ** 2))
        
        self.conv_blocks = nn.Sequential(
            nn.BatchNorm2d(128),
            nn.Upsample(scale_factor=2),
            nn.Conv2d(128, 128, 3, stride=1, padding=1),
            nn.BatchNorm2d(128, 0.8),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Upsample(scale_factor=2),
            nn.Conv2d(128, 64, 3, stride=1, padding=1),
            nn.BatchNorm2d(64, 0.8),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(64, 3, 3, stride=1, padding=1),
            nn.Tanh(),
        )

    def forward(self, z):
        out = self.l1(z)
        out = out.view(out.shape[0], 128, self.init_size, self.init_size)
        img = self.conv_blocks(out)
        return img

class Discriminator(nn.Module):
    def __init__(self):
        super(Discriminator, self).__init__()

        def discriminator_block(in_filters, out_filters, bn=True):
            block = [nn.Conv2d(in_filters, out_filters, 3, 2, 1), nn.LeakyReLU(0.2, inplace=True), nn.Dropout2d(0.25)]
            if bn:
                block.append(nn.BatchNorm2d(out_filters, 0.8))
            return block

        self.model = nn.Sequential(
            *discriminator_block(3, 16, bn=False),
            *discriminator_block(16, 32),
            *discriminator_block(32, 64),
            *discriminator_block(64, 128),
        )

        ds_size = 64 // 2 ** 4
        self.adv_layer = nn.Sequential(nn.Linear(128 * ds_size ** 2, 1), nn.Sigmoid())

    def forward(self, img):
        out = self.model(img)
        out = out.view(out.shape[0], -1)
        validity = self.adv_layer(out)
        return validity

def run_gan_training(config):
    print("[Agent 1 - GAN] Starting GAN Data Augmentor Training")
    
    latent_dim = config['gan']['latent_dim']
    lr = config['gan']['learning_rate']
    b1 = 0.5
    b2 = 0.999
    epochs = config['gan']['epochs']
    batch_size = config['gan']['batch_size']
    image_size = config['gan']['image_size']
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Agent 1 - GAN] Using device: {device}")

    # Initialize generator and discriminator
    generator = Generator(latent_dim).to(device)
    discriminator = Discriminator().to(device)

    # Loss function
    adversarial_loss = nn.BCELoss().to(device)

    # Optimizers
    optimizer_G = torch.optim.Adam(generator.parameters(), lr=lr, betas=(b1, b2))
    optimizer_D = torch.optim.Adam(discriminator.parameters(), lr=lr, betas=(b1, b2))

    # Configure data loader
    os.makedirs("data/raw", exist_ok=True)
    
    # Check if data/raw has subfolders (classes). If not, we can't use ImageFolder easily, so we fallback.
    subfolders = [f.path for f in os.scandir("data/raw") if f.is_dir()]
    if len(subfolders) == 0:
        print("[Agent 1 - GAN] WARNING: No class subfolders found in data/raw. Creating a dummy 'class0' folder.")
        os.makedirs("data/raw/class0", exist_ok=True)
        # Create a dummy image if none exist
        from PIL import Image
        import numpy as np
        if len(os.listdir("data/raw/class0")) == 0:
            dummy_img = Image.fromarray(np.uint8(np.random.rand(64,64,3)*255))
            dummy_img.save("data/raw/class0/dummy.png")
            
    transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize([0.5], [0.5])
    ])
    
    dataset = datasets.ImageFolder(root="data/raw", transform=transform)
    
    if len(dataset) == 0:
        print("[Agent 1 - GAN] WARNING: Dataset is empty. Cannot train.")
        return
        
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        drop_last=True if len(dataset) >= batch_size else False
    )

    print(f"[Agent 1 - GAN] Training on {len(dataset)} images for {epochs} epochs.")

    try:
        for epoch in range(epochs):
            for i, (imgs, _) in enumerate(dataloader):
                valid = torch.ones((imgs.size(0), 1), requires_grad=False, device=device)
                fake = torch.zeros((imgs.size(0), 1), requires_grad=False, device=device)
                real_imgs = imgs.to(device)
    
                # -----------------
                #  Train Generator
                # -----------------
                optimizer_G.zero_grad()
                z = torch.randn((imgs.size(0), latent_dim), device=device)
                gen_imgs = generator(z)
                g_loss = adversarial_loss(discriminator(gen_imgs), valid)
                g_loss.backward()
                optimizer_G.step()
    
                # ---------------------
                #  Train Discriminator
                # ---------------------
                optimizer_D.zero_grad()
                real_loss = adversarial_loss(discriminator(real_imgs), valid)
                fake_loss = adversarial_loss(discriminator(gen_imgs.detach()), fake)
                d_loss = (real_loss + fake_loss) / 2
                d_loss.backward()
                optimizer_D.step()
    
            if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
                print(f"[Agent 1 - GAN] Epoch {epoch+1}/{epochs} | D loss: {d_loss.item():.4f} | G loss: {g_loss.item():.4f}")
    
        # Save checkpoint
        os.makedirs("output/checkpoints", exist_ok=True)
        torch.save(generator.state_dict(), "output/checkpoints/generator.pth")
        print("[Agent 1 - GAN] Checkpoint saved.")
    except Exception as e:
        print(f"[Agent 1 - GAN] Training interrupted: {e}")
    finally:
        os.makedirs("output/checkpoints", exist_ok=True)
        torch.save(generator.state_dict(), "output/checkpoints/generator_emergency.pth")
        print("[Agent 1 - GAN] Emergency checkpoint saved.")

def generate_synthetic_data(config):
    print("[Agent 1 - GAN] Generating synthetic data...")
    latent_dim = config['gan']['latent_dim']
    image_size = config['gan']['image_size']
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    generator = Generator(latent_dim).to(device)
    ckpt_path = "output/checkpoints/generator.pth"
    if os.path.exists(ckpt_path):
        generator.load_state_dict(torch.load(ckpt_path, map_location=device))
    else:
        print("[Agent 1 - GAN] WARNING: No checkpoint found, using random weights.")
    
    generator.eval()
    
    # Calculate how many to generate based on original dataset size * multiplier
    dataset_size = 0
    if os.path.exists("data/raw"):
        for root, _, files in os.walk("data/raw"):
            dataset_size += sum(1 for f in files if f.endswith(('.png', '.jpg', '.jpeg')))
            
    num_images = int(max(config['gan']['batch_size'], dataset_size * config['gan']['synthetic_multiplier']))
    
    os.makedirs("output/synthetic_data", exist_ok=True)
    
    with torch.no_grad():
        for i in range(num_images):
            z = torch.randn(1, latent_dim, device=device)
            img = generator(z)
            # Rescale images from [-1, 1] to [0, 1]
            img = (img + 1) / 2
            save_image(img.data, f"output/synthetic_data/synthetic_{i:04d}.png")
    
    print(f"[Agent 1 - GAN] Generated {num_images} synthetic images.")
