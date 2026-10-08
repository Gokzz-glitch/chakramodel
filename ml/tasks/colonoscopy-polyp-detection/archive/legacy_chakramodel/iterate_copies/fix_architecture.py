import json

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# The correct class definition based on the user's source code
correct_class = """class ChakraTransformerSegmenter(nn.Module):
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=False, num_classes=1):
        super(ChakraTransformerSegmenter, self).__init__()
        self.backbone = timm.create_model(
            backbone_name, 
            pretrained=pretrained, 
            features_only=False,
            drop_rate=0.1,
            attn_drop_rate=0.1
        )
        self.embed_dim = self.backbone.embed_dim
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1)
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def forward(self, x):
        import torch.nn.functional as F
        B, C, H, W = x.shape
        features = self.backbone.forward_features(x)
        if features.dim() == 3:
            if features.shape[1] == (H // 16) * (W // 16) + 1:
                features = features[:, 1:]
            grid_h = H // 16
            grid_w = W // 16
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)
            
        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2:
                x_dec = self.dropout1(x_dec)
            elif i == 5:
                x_dec = self.dropout2(x_dec)
        logits = x_dec
        if logits.shape[2:] != (H, W):
            logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)
        return logits"""

load_logic = """try:
    vit_model = ChakraTransformerSegmenter().to(device)
    state_dict = torch.load(VIT_WEIGHTS, map_location=device)
    raw_dict = state_dict.get('model_state_dict', state_dict)
    
    # Strip the DataParallel 'module.' prefix
    new_dict = {k.replace('module.', ''): v for k, v in raw_dict.items()}
        
    vit_model.load_state_dict(new_dict, strict=True)
    vit_model.eval()
except Exception as e:
    vit_model = None
    print(f"ViT weights not found or error loading: {e}")"""

# We need to replace the cell containing the model definition entirely to avoid string replacement nightmares
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'class ChakraTransformerSegmenter' in ''.join(cell['source']):
        # Construct the new cell source
        new_source = [
            "import torch\n",
            "import torch.nn as nn\n",
            "import timm\n",
            "import cv2\n",
            "import numpy as np\n",
            "import time\n",
            "from ultralytics import YOLO\n",
            "import matplotlib.pyplot as plt\n",
            "import albumentations as A\n",
            "from albumentations.pytorch import ToTensorV2\n\n",
            "device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')\n",
            "print(f'Targeting device: {device}')\n\n",
            correct_class + "\n\n",
            "# Load Weights\n",
            "try:\n",
            "    yolo_model = YOLO(YOLO_WEIGHTS)\n",
            "except:\n",
            "    yolo_model = None\n",
            "    print('YOLO weights not found.')\n\n",
            load_logic + "\n\n",
            "vit_transforms = A.Compose([\n",
            "    A.Resize(384, 384),\n",
            "    A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),\n",
            "    ToTensorV2()\n",
            "])"
        ]
        
        # Proper line formatting
        formatted_source = []
        for line in "".join(new_source).split('\n'):
            formatted_source.append(line + '\n')
        formatted_source[-1] = formatted_source[-1].rstrip('\n')
        
        cell['source'] = formatted_source
        break

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
