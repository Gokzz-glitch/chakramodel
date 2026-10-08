import torch
import torch.nn as nn
import torch.optim as optim
import os
from data_loader import get_dataloader
from watermark_gan import Encoder, Decoder, Discriminator

def train(epochs=1, batch_size=64, message_length=16, save_dir='./checkpoints'):
    os.makedirs(save_dir, exist_ok=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    loader = get_dataloader(batch_size=batch_size)
    
    encoder = Encoder(message_length).to(device)
    decoder = Decoder(message_length).to(device)
    discriminator = Discriminator().to(device)
    
    # Optimizers
    opt_ed = optim.Adam(list(encoder.parameters()) + list(decoder.parameters()), lr=1e-3)
    opt_d = optim.Adam(discriminator.parameters(), lr=1e-3)
    
    # Losses
    mse_loss = nn.MSELoss()
    bce_loss = nn.BCEWithLogitsLoss()
    
    # Hyperparameters for loss weighting
    lambda_i = 10.0   # Image reconstruction weight
    lambda_m = 1.0    # Message extraction weight
    lambda_a = 0.001  # Adversarial weight
    
    print("Starting Training...")
    for epoch in range(epochs):
        for i, (images, _) in enumerate(loader):
            images = images.to(device)
            batch_size_actual = images.size(0)
            
            # Generate random binary message
            messages = torch.randint(0, 2, (batch_size_actual, message_length)).float().to(device)
            
            # ---------------------
            #  Train Discriminator
            # ---------------------
            opt_d.zero_grad()
            
            # Real images
            real_preds = discriminator(images)
            d_loss_real = mse_loss(real_preds, torch.ones_like(real_preds))
            
            # Watermarked images (fake)
            watermarked = encoder(images, messages)
            fake_preds = discriminator(watermarked.detach())
            d_loss_fake = mse_loss(fake_preds, torch.zeros_like(fake_preds))
            
            d_loss = (d_loss_real + d_loss_fake) / 2
            d_loss.backward()
            opt_d.step()
            
            # ---------------------
            #  Train Encoder & Decoder
            # ---------------------
            opt_ed.zero_grad()
            
            # Adversarial Loss (try to fool discriminator)
            fake_preds_for_g = discriminator(watermarked)
            loss_adv = mse_loss(fake_preds_for_g, torch.ones_like(fake_preds_for_g))
            
            # Image Reconstruction Loss
            loss_img = mse_loss(watermarked, images)
            
            # Message Extraction Loss
            extracted_msg = decoder(watermarked)
            loss_msg = bce_loss(extracted_msg, messages)
            
            # Total Encoder/Decoder loss
            ed_loss = lambda_i * loss_img + lambda_m * loss_msg + lambda_a * loss_adv
            ed_loss.backward()
            opt_ed.step()
            
            # Calculate Bit Error Rate (BER) for monitoring
            with torch.no_grad():
                preds = (torch.sigmoid(extracted_msg) > 0.5).float()
                ber = (preds != messages).float().mean().item()
            
            if i % 100 == 0:
                print(f"[Epoch {epoch}/{epochs}] [Batch {i}/{len(loader)}] "
                      f"[D loss: {d_loss.item():.4f}] "
                      f"[ED loss: {ed_loss.item():.4f}] "
                      f"[Img loss: {loss_img.item():.4f}] "
                      f"[Msg loss: {loss_msg.item():.4f}] "
                      f"[BER: {ber:.4f}]")
                
        # Save checkpoints
        torch.save(encoder.state_dict(), os.path.join(save_dir, f'encoder_epoch_{epoch}.pth'))
        torch.save(decoder.state_dict(), os.path.join(save_dir, f'decoder_epoch_{epoch}.pth'))
        torch.save(discriminator.state_dict(), os.path.join(save_dir, f'discriminator_epoch_{epoch}.pth'))
        
    print("Training Complete!")

if __name__ == "__main__":
    train(epochs=1, batch_size=64)
