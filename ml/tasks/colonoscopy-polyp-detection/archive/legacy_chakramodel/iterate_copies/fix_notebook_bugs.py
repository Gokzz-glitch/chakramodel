import json

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# 1. Update the ViT weight loading cell
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'class ChakraTransformerSegmenter' in ''.join(cell['source']):
        source_str = "".join(cell['source'])
        
        # Replace the weight loading logic
        old_load_logic = """    state_dict = torch.load(VIT_WEIGHTS, map_location=device)\n    vit_model.load_state_dict(state_dict.get('model_state_dict', state_dict))\n    vit_model.eval()"""
        new_load_logic = """    state_dict = torch.load(VIT_WEIGHTS, map_location=device)\n    raw_dict = state_dict.get('model_state_dict', state_dict)\n    \n    # Fix DataParallel and naming mismatches in the saved weights\n    new_dict = {}\n    for k, v in raw_dict.items():\n        k = k.replace('module.', '')\n        k = k.replace('backbone.', 'encoder.')\n        k = k.replace('decode_head.', 'decoder.')\n        new_dict[k] = v\n        \n    vit_model.load_state_dict(new_dict, strict=False)\n    vit_model.eval()"""
        
        source_str = source_str.replace(old_load_logic, new_load_logic)
        
        # Write back line by line to preserve formatting
        cell['source'] = [line + '\n' for line in source_str.split('\n')]
        # Remove trailing newline from the last line
        if cell['source']:
            cell['source'][-1] = cell['source'][-1].rstrip('\n')
            
# 2. Update the Video processing cell
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'process_video_benchmark(input_video_path' in ''.join(cell['source']):
        source_str = "".join(cell['source'])
        
        old_video_check = "if os.path.exists(VIDEO_DATASET):"
        new_video_check = "if VIDEO_DATASET and os.path.exists(VIDEO_DATASET):"
        
        source_str = source_str.replace(old_video_check, new_video_check)
        
        cell['source'] = [line + '\n' for line in source_str.split('\n')]
        if cell['source']:
            cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
