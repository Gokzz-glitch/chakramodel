import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.utils as vutils
import matplotlib.pyplot as plt
import numpy as np
import os
from data_loader import get_dataloaders

# ----------------- INVARIANTS -----------------
# 1. Random Weight Initialization
# 2. Built entirely from scratch
# 3. No pre-trained weights
# ----------------------------------------------

def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        nn.init.normal_(m.weight.data, 0.0, 0.02)
    elif classname.find('BatchNorm') != -1:
        nn.init.normal_(m.weight.data, 1.0, 0.02)
        nn.init.constant_(m.bias.data, 0)

class Constructor(nn.Module):
    def __init__(self, nz=100, ngf=64, nc=3):
        super(Constructor, self).__init__()
        self.main = nn.Sequential(
            # input is Z, going into a convolution
            nn.ConvTranspose2d(nz, ngf * 8, 4, 1, 0, bias=False),
            nn.BatchNorm2d(ngf * 8),
            nn.ReLU(True),
            # state size. (ngf*8) x 4 x 4
            nn.ConvTranspose2d(ngf * 8, ngf * 4, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf * 4),
            nn.ReLU(True),
            # state size. (ngf*4) x 8 x 8
            nn.ConvTranspose2d(ngf * 4, ngf * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf * 2),
            nn.ReLU(True),
            # state size. (ngf*2) x 16 x 16
            nn.ConvTranspose2d(ngf * 2, ngf, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf),
            nn.ReLU(True),
            # state size. (ngf) x 32 x 32
            nn.ConvTranspose2d(ngf, nc, 4, 2, 1, bias=False),
            nn.Tanh()
            # state size. (nc) x 64 x 64
        )

    def forward(self, input):
        return self.main(input)


class Destructor(nn.Module):
    def __init__(self, nc=3, ndf=64):
        super(Destructor, self).__init__()
        self.main = nn.Sequential(
            # input is (nc) x 64 x 64
            nn.Conv2d(nc, ndf, 4, 2, 1, bias=False),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf) x 32 x 32
            nn.Conv2d(ndf, ndf * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ndf * 2),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*2) x 16 x 16
            nn.Conv2d(ndf * 2, ndf * 4, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ndf * 4),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*4) x 8 x 8
            nn.Conv2d(ndf * 4, ndf * 8, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ndf * 8),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*8) x 4 x 4
            nn.Conv2d(ndf * 8, 1, 4, 1, 0, bias=False),
            nn.Sigmoid()
        )

    def forward(self, input):
        return self.main(input).view(-1, 1).squeeze(1)


def train_gan(num_epochs=20): # Using small epochs for prototype hackathon speed
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True

    # Increased batch size to 512 to maximize GPU utilization
    train_dl, _ = get_dataloaders(batch_size=512)

    nz = 100
    netG = Constructor().to(device)
    netG.apply(weights_init)

    netD = Destructor().to(device)
    netD.apply(weights_init)

    criterion = nn.BCELoss()
    fixed_noise = torch.randn(64, nz, 1, 1, device=device)
    real_label = 1.0
    fake_label = 0.0

    optimizerD = optim.Adam(netD.parameters(), lr=0.0002, betas=(0.5, 0.999))
    optimizerG = optim.Adam(netG.parameters(), lr=0.0002, betas=(0.5, 0.999))

    os.makedirs("outputs", exist_ok=True)
    os.makedirs("checkpoints", exist_ok=True)

    print("Starting Training Loop...")
    for epoch in range(num_epochs):
        for i, data in enumerate(train_dl, 0):
            # Format batch
            real_cpu = data[0].to(device)
            b_size = real_cpu.size(0)
            label = torch.full((b_size,), real_label, dtype=torch.float, device=device)

            # (1) Update D network: maximize log(D(x)) + log(1 - D(G(z)))
            netD.zero_grad()
            output = netD(real_cpu)
            errD_real = criterion(output, label)
            errD_real.backward()
            D_x = output.mean().item()

            noise = torch.randn(b_size, nz, 1, 1, device=device)
            fake = netG(noise)
            label.fill_(fake_label)
            output = netD(fake.detach())
            errD_fake = criterion(output, label)
            errD_fake.backward()
            D_G_z1 = output.mean().item()
            errD = errD_real + errD_fake
            optimizerD.step()

            # (2) Update G network: maximize log(D(G(z)))
            netG.zero_grad()
            label.fill_(real_label)  # fake labels are real for generator cost
            output = netD(fake)
            errG = criterion(output, label)
            errG.backward()
            D_G_z2 = output.mean().item()
            optimizerG.step()

            if i % 10 == 0:
                print(f'[{epoch}/{num_epochs}][{i}/{len(train_dl)}] '
                      f'Loss_D: {errD.item():.4f} Loss_G: {errG.item():.4f} '
                      f'D(x): {D_x:.4f} D(G(z)): {D_G_z1:.4f} / {D_G_z2:.4f}')

        # Save Checkpoint & Image every 5 epochs or last epoch
        if epoch % 5 == 0 or epoch == num_epochs - 1:
            with torch.no_grad():
                fake = netG(fixed_noise).detach().cpu()
                
            # Plot side by side
            real_batch = next(iter(train_dl))[0][:32].to(device)
            fig, axes = plt.subplots(1, 2, figsize=(15, 8))
            axes[0].axis("off")
            axes[0].set_title("Real Images")
            axes[0].imshow(np.transpose(vutils.make_grid(real_batch, padding=5, normalize=True).cpu(), (1, 2, 0)))

            axes[1].axis("off")
            axes[1].set_title("DataGuard Generated Images (Fake)")
            axes[1].imshow(np.transpose(vutils.make_grid(fake[:32], padding=5, normalize=True).cpu(), (1, 2, 0)))

            plt.savefig(f'outputs/gan_epoch_{epoch}.png')
            plt.close()
            
            torch.save(netG.state_dict(), f'checkpoints/netG_epoch_{epoch}.pth')
            torch.save(netD.state_dict(), f'checkpoints/netD_epoch_{epoch}.pth')

            # Halt logic if Destructor is completely confused (Loss ~ 1.38 which is 2 * 0.69)
            if abs(errD.item() - 1.386) < 0.1:
                print("Destructor loss reached convergence (unable to tell real from fake). Halting GAN training early.")
                break

if __name__ == '__main__':
    train_gan(num_epochs=10)
