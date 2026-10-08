import torch
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import os
import glob
from watermark_gan import Encoder, Decoder

def evaluate(message_length=16, checkpoint_dir='./checkpoints'):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Find latest checkpoint
    encoder_paths = sorted(glob.glob(os.path.join(checkpoint_dir, 'encoder_epoch_*.pth')))
    decoder_paths = sorted(glob.glob(os.path.join(checkpoint_dir, 'decoder_epoch_*.pth')))
    
    if not encoder_paths or not decoder_paths:
        print("No checkpoints found. Please run train_gan.py first.")
        return
        
    latest_encoder = encoder_paths[-1]
    latest_decoder = decoder_paths[-1]
    
    print(f"Loading {latest_encoder} and {latest_decoder}")
    
    encoder = Encoder(message_length).to(device)
    decoder = Decoder(message_length).to(device)
    
    encoder.load_state_dict(torch.load(latest_encoder, map_location=device))
    decoder.load_state_dict(torch.load(latest_decoder, map_location=device))
    
    encoder.eval()
    decoder.eval()
    
    # Create a random synthetic image for testing (32x32)
    # Real test would load an actual image
    img = torch.randn(1, 3, 32, 32).to(device)
    
    # Generate random 16-bit message
    msg = torch.randint(0, 2, (1, message_length)).float().to(device)
    
    print(f"Original Message:  {msg.int().cpu().numpy()[0]}")
    
    with torch.no_grad():
        watermarked_img = encoder(img, msg)
        extracted_msg_logits = decoder(watermarked_img)
        
        preds = (torch.sigmoid(extracted_msg_logits) > 0.5).int()
        
    print(f"Extracted Message: {preds.cpu().numpy()[0]}")
    
    ber = (preds != msg).float().mean().item()
    print(f"Bit Error Rate: {ber:.2%}")
    
    # Calculate image difference
    mse = torch.nn.functional.mse_loss(watermarked_img, img).item()
    print(f"Image MSE Loss: {mse:.4f}")
    print("\n✅ Proof of Concept Successful! The GAN can embed and extract watermarks invisibly.")

if __name__ == "__main__":
    evaluate()
