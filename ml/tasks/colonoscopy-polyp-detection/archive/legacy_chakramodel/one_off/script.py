import json
import os
import glob
import re

notebooks = [
    'deprecated/Combo2_Topo_ChakraNet.ipynb',
    'deprecated/Combo3_AdaBN_ChakraNet.ipynb',
    'deprecated/Combo4_DiffusionAug_ChakraNet.ipynb',
    'deprecated/Combo5_Federated_ChakraNet.ipynb',
    'Combo1_ChakraNet_Focal.ipynb',
    'Combo6_ChakraTransformer.ipynb',
    'Kaggle_CrossVal_v5_PATHS_FIXED.ipynb',
    'Kaggle_Final_Proof_Eval.ipynb'
]

base_dir = r'M:\chakramodel\notebooks'
results = []

for nb_name in notebooks:
    path = os.path.join(base_dir, nb_name)
    if not os.path.exists(path):
        results.append(f"## {nb_name}\n- **Executed**: N/A (File not found)\n")
        continue
    
    with open(path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    has_outputs = False
    model_types = set()
    datasets = set()
    platforms = set()
    metrics = []
    combo_evidence = []
    
    epochs = '?'
    bs = '?'
    lr = '?'
    
    for cell in nb.get('cells', []):
        if cell['cell_type'] == 'code':
            source = ''.join(cell.get('source', []))
            outputs = cell.get('outputs', [])
            
            if outputs:
                has_outputs = True
                for out in outputs:
                    text = ''
                    if 'text' in out:
                        text = ''.join(out['text'])
                    elif 'data' in out and 'text/plain' in out['data']:
                        text = ''.join(out['data']['text/plain'])
                    
                    if text:
                        m = re.findall(r'(Dice|IoU|loss|Loss)[:=]?\s*([0-9]+\.[0-9]+)', text)
                        if m:
                            metrics.extend(m)
            
            # Platform
            if '/kaggle/input' in source or '/kaggle/working' in source: platforms.add('Kaggle')
            if '/content/' in source: platforms.add('Colab')
            if 'C:\\' in source or 'M:\\' in source or './data' in source: platforms.add('Local')
            
            # Model
            if 'ChakraNet' in source: model_types.add('ChakraNet')
            if 'Transformer' in source: model_types.add('Transformer')
            if 'PraNet' in source: model_types.add('PraNet')
            
            # Dataset
            if 'kvasir-seg' in source.lower(): datasets.add('kvasir-seg')
            if 'cvc-clinicdb' in source.lower() or 'cvc_clinicdb' in source.lower(): datasets.add('cvc-clinicdb')
            
            # Config
            m_ep = re.search(r'epochs?\s*=\s*([0-9]+)', source, re.I)
            if m_ep: epochs = m_ep.group(1)
            m_bs = re.search(r'batch_size?\s*=\s*([0-9]+)', source, re.I)
            if m_bs: bs = m_bs.group(1)
            m_lr = re.search(r'lr?\s*=\s*([0-9e.-]+)', source, re.I)
            if m_lr: lr = m_lr.group(1)
            
            # Combo evidence
            if 'Combo2' in nb_name and ('Topological' in source or 'Betti' in source): combo_evidence.append('Topo Loss found')
            if 'Combo3' in nb_name and ('AdaBN' in source or 'TargetDomain' in source): combo_evidence.append('AdaBN found')
            if 'Combo4' in nb_name and ('StableDiffusion' in source or 'ControlNet' in source or 'MC Dropout' in source): combo_evidence.append('Diffusion/Dropout found')
            if 'Combo5' in nb_name and ('FedAvg' in source or 'federated' in source.lower()): combo_evidence.append('Federated found')

    executed = "YES" if has_outputs else "NO"
    platform = " / ".join(platforms) if platforms else "Local"
    model = " / ".join(model_types) if model_types else "Unknown"
    dataset = " / ".join(datasets) if datasets else "Unknown"
    metric_str = ", ".join([f"{k}={v}" for k, v in list(set(metrics))[:5]]) if metrics else "NONE"
    
    is_combo_impl = "YES" if combo_evidence else "NO"
    if 'Combo' not in nb_name: is_combo_impl = "N/A"
    evidence = ' + '.join(list(set(combo_evidence))) if combo_evidence else "Template copy or no specific logic"
    
    verdict = "REAL_TRAINED" if has_outputs and metrics else ("PARTIAL" if has_outputs else "TEMPLATE_ONLY")
    
    res = f"## {nb_name}\n"
    res += f"- **Executed**: {executed}\n"
    res += f"- **Platform**: {platform}\n"
    res += f"- **Model**: {model}\n"
    res += f"- **Dataset**: {dataset}\n"
    res += f"- **Training config**: epochs={epochs}, bs={bs}, lr={lr}\n"
    res += f"- **Metrics in outputs**: {metric_str}\n"
    res += f"- **Combo variant implemented**: {is_combo_impl} ({evidence})\n"
    res += f"- **Verdict**: {verdict}\n"
    results.append(res)

print('\n'.join(results))
