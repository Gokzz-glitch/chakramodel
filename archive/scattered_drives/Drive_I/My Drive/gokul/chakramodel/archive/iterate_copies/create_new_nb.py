import json

source_notebook = r"C:\Users\imgk3\Downloads\om-krish-4 (4).ipynb"
target_notebook = r"C:\Users\imgk3\Downloads\ChakraTransformer_MultiGPU_Final.ipynb"

with open(source_notebook, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and len(cell['source']) > 0:
        if cell['source'][0].startswith('%%writefile src/chakra_transformer/train_transformer.py'):
            # Reconstruct the train_transformer.py to guarantee perfect indentation
            new_code = []
            for line in cell['source']:
                if 'device = torch.device("cuda")' in line:
                    new_code.append(line)
                    new_code.append('    model = ChakraTransformerSegmenter().to(device)\n')
                    new_code.append('    \n')
                    new_code.append('    if torch.cuda.device_count() > 1:\n')
                    new_code.append('        model = nn.DataParallel(model)\n')
                    new_code.append('        \n')
                elif 'model = ChakraTransformerSegmenter().to(device)' in line:
                    pass # We added this above
                elif 'if torch.cuda.device_count() > 1:' in line or 'model = nn.DataParallel(model)' in line:
                    pass # Skip if any mangled lines are left
                else:
                    new_code.append(line)
            cell['source'] = new_code
        
        elif 'os.system("python src/chakra_transformer/train_transformer.py' in ''.join(cell['source']):
            new_exec = []
            for line in cell['source']:
                if '--batch-size' in line:
                    new_exec.append('    os.system("python src/chakra_transformer/train_transformer.py --epochs 100 --batch-size 16")\n')
                else:
                    new_exec.append(line)
            cell['source'] = new_exec
            
with open(target_notebook, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Created new notebook successfully!")
