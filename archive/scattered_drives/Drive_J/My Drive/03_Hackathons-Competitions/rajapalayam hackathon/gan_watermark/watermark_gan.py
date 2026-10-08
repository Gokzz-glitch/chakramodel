import torch
import torch.nn as nn
import torch.nn.functional as F

class Encoder(nn.Module):
    def __init__(self, message_length=16):
        super(Encoder, self).__init__()
        # Input: image (3 channels) + message (message_length channels)
        # We will expand the message spatially to match image size (32x32)
        self.message_length = message_length
        
        self.conv1 = nn.Conv2d(3 + message_length, 64, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(64, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(64, 3, kernel_size=3, padding=1)
        
    def forward(self, image, message):
        # image: (B, 3, 32, 32)
        # message: (B, message_length)
        
        # Expand message to (B, message_length, 32, 32)
        msg_expanded = message.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 32, 32)
        
        # Concatenate image and expanded message
        x = torch.cat([image, msg_expanded], dim=1)
        
        # Pass through conv layers
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        # Add residual connection to original image to help invisibility
        residual = self.conv3(x)
        
        watermarked_image = image + residual
        
        # Tanh to keep it in [-1, 1] range (same as input)
        return torch.tanh(watermarked_image)


class Decoder(nn.Module):
    def __init__(self, message_length=16):
        super(Decoder, self).__init__()
        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=2, padding=1) # 16x16
        self.conv2 = nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1) # 8x8
        self.conv3 = nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1) # 4x4
        self.fc = nn.Linear(256 * 4 * 4, message_length)
        
    def forward(self, watermarked_image):
        x = F.relu(self.conv1(watermarked_image))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = x.view(x.size(0), -1)
        # output raw logits for message
        return self.fc(x)


class Discriminator(nn.Module):
    def __init__(self):
        super(Discriminator, self).__init__()
        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=2, padding=1) # 16x16
        self.conv2 = nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1) # 8x8
        self.conv3 = nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1) # 4x4
        self.fc = nn.Linear(256 * 4 * 4, 1)
        
    def forward(self, image):
        x = F.leaky_relu(self.conv1(image), 0.2)
        x = F.leaky_relu(self.conv2(x), 0.2)
        x = F.leaky_relu(self.conv3(x), 0.2)
        x = x.view(x.size(0), -1)
        return self.fc(x)

if __name__ == "__main__":
    # Quick test of shapes
    img = torch.randn(2, 3, 32, 32)
    msg = torch.randint(0, 2, (2, 16)).float()
    
    encoder = Encoder()
    decoder = Decoder()
    discriminator = Discriminator()
    
    watermarked = encoder(img, msg)
    extracted_msg = decoder(watermarked)
    validity = discriminator(watermarked)
    
    print(f"Original image shape: {img.shape}")
    print(f"Watermarked image shape: {watermarked.shape}")
    print(f"Extracted message shape: {extracted_msg.shape}")
    print(f"Discriminator output shape: {validity.shape}")
