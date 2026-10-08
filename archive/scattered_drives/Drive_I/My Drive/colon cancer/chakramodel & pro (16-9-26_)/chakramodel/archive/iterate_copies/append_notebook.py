import json

from pathlib import Path
root = Path(__file__).resolve().parent
nb_path = root / 'notebooks' / 'Kaggle_ChakraTransformer_Evaluation.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

cells = nb.get('cells', [])

cells.append({
    'cell_type': 'markdown',
    'metadata': {},
    'source': [
        '## Video Inference on polypdataset-gokul\n',
        '\n',
        'Run the ChakraTransformer on all `.mp4` and `.avi` videos from the dataset and save the annotated videos.'
    ]
})

cells.append({
    'cell_type': 'code',
    'execution_count': None,
    'metadata': {},
    'outputs': [],
    'source': [
        'import cv2\n',
        'import numpy as np\n',
        'from torchvision import transforms\n',
        'import time\n',
        '\n',
        'video_dir = Path(\'/kaggle/input/polypdataset-gokul\')\n',
        'output_dir = Path(\'/kaggle/working/output_videos\')\n',
        'output_dir.mkdir(parents=True, exist_ok=True)\n',
        '\n',
        'video_files = list(video_dir.glob(\'*.mp4\')) + list(video_dir.glob(\'*.avi\'))\n',
        'print(f\"Found {len(video_files)} videos for testing.\")\n',
        '\n',
        'transform = transforms.Compose([\n',
        '    transforms.ToPILImage(),\n',
        '    transforms.Resize((448, 448)),\n',
        '    transforms.ToTensor(),\n',
        '])\n',
        '\n',
        'for vid_path in video_files:\n',
        '    print(f\"\\nProcessing {vid_path.name}...\")\n',
        '    cap = cv2.VideoCapture(str(vid_path))\n',
        '    \n',
        '    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))\n',
        '    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))\n',
        '    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0\n',
        '    \n',
        '    out_path = str(output_dir / f\"annotated_{vid_path.name}\")\n',
        '    fourcc = cv2.VideoWriter_fourcc(*\'mp4v\')\n',
        '    out = cv2.VideoWriter(out_path, fourcc, int(fps), (width, height))\n',
        '    \n',
        '    frame_count = 0\n',
        '    start_time = time.time()\n',
        '    \n',
        '    while cap.isOpened():\n',
        '        ret, frame = cap.read()\n',
        '        if not ret:\n',
        '            break\n',
        '            \n',
        '        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)\n',
        '        input_tensor = transform(rgb_frame).unsqueeze(0).to(device)\n',
        '        \n',
        '        with torch.no_grad():\n',
        '            outputs = model(input_tensor)\n',
        '            if isinstance(outputs, (tuple, list)):\n',
        '                pred = outputs[0]\n',
        '            else:\n',
        '                pred = outputs\n',
        '            pred = torch.sigmoid(pred).squeeze().cpu().numpy()\n',
        '            \n',
        '        pred_resized = cv2.resize(pred, (width, height))\n',
        '        mask = (pred_resized > 0.5).astype(np.uint8) * 255\n',
        '        \n',
        '        colored_mask = np.zeros_like(frame)\n',
        '        colored_mask[:, :, 1] = mask\n',
        '        \n',
        '        overlay = cv2.addWeighted(frame, 0.7, colored_mask, 0.3, 0)\n',
        '        out.write(overlay)\n',
        '        \n',
        '        frame_count += 1\n',
        '        if frame_count % 50 == 0:\n',
        '            print(f\"  Processed {frame_count} frames...\")\n',
        '            \n',
        '    cap.release()\n',
        '    out.release()\n',
        '    elapsed = time.time() - start_time\n',
        '    print(f\"Finished {vid_path.name} - {frame_count} frames in {elapsed:.2f}s ({frame_count/elapsed:.1f} FPS)\")\n',
        '    print(f\"Saved to {out_path}\")\n'
    ]
})

nb['cells'] = cells

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Notebook appended successfully.")
