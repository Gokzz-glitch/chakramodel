import torch
import torch.nn as nn

class TemporalProposer(nn.Module):
    """
    Stage 1: The Temporal Proposer.
    Ingests a volumetric window (e.g. 64 frames) and uses 3D self-attention 
    to track features across pixels and time.
    """
    def __init__(self, embed_dim=128):
        super().__init__()
        # Mock representation of a Video Swin Transformer / VideoMAE V2
        self.tubelet_embedder = nn.Conv3d(
            in_channels=3, out_channels=embed_dim, kernel_size=(4, 4, 4), stride=(4, 4, 4)
        )
        self.transformer_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=embed_dim, nhead=8, dim_feedforward=512, batch_first=True),
            num_layers=4
        )
        
        # Outputs 3D spatio-temporal bounding box prompts: (batch, num_prompts, 6)
        # where 6 corresponds to [t_start, t_end, y_min, x_min, y_max, x_max]
        self.prompt_head = nn.Linear(embed_dim, 6)

    def forward(self, x):
        """
        Args:
            x: Tensor of shape (B, C, T, H, W)
        Returns:
            prompts: Tensor of shape (B, num_prompts, 6)
        """
        B, C, T, H, W = x.shape
        # Embed tubelets
        embedded = self.tubelet_embedder(x) # (B, embed_dim, T', H', W')
        B, D, T_prime, H_prime, W_prime = embedded.shape
        
        # Pool spatial dimensions to prevent OOM in transformer (mocking hierarchical pooling)
        import torch.nn.functional as F
        pooled = F.adaptive_avg_pool3d(embedded, (T_prime, 4, 4))
        
        # Flatten spatio-temporal dimensions
        embedded_flat = pooled.view(B, D, -1).permute(0, 2, 1) # (B, N, D)
        
        # Process through transformer
        encoded = self.transformer_encoder(embedded_flat)
        
        # Generate prompts (mock output for architecture scaffolding)
        # In reality, this would use a Hungarian matcher or dense head like DETR
        prompts = self.prompt_head(encoded) 
        
        # Take top 5 prompts for demonstration
        top_prompts = prompts[:, :5, :] 
        return top_prompts
