"""Extract the YAML architecture from the pickle data"""
import zipfile
import pickle
import io

zip_path = r'C:\Users\imgk3\Downloads\best.zip'

with zipfile.ZipFile(zip_path, 'r') as zf:
    pkl_data = zf.read('best/data.pkl')

class InspectorUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == 'collections' and name == 'OrderedDict':
            from collections import OrderedDict
            return OrderedDict
        if '_rebuild' in name:
            def dummy_rebuild(*args, **kwargs):
                return f"<TENSOR>"
            return dummy_rebuild
        if 'Storage' in name or 'storage' in module:
            class DummyStorage:
                def __init__(self, *args, **kwargs): pass
                def __setstate__(self, state): pass
            return DummyStorage
        class DummyClass:
            def __init__(self, *args, **kwargs):
                self._init_args = args
                self._init_kwargs = kwargs
            def __setstate__(self, state):
                if isinstance(state, dict):
                    self.__dict__.update(state)
        DummyClass.__name__ = name
        DummyClass.__module__ = module
        return DummyClass
    def persistent_load(self, pid):
        return f"<STORAGE:{pid}>"

unpickler = InspectorUnpickler(io.BytesIO(pkl_data))
result = unpickler.load()

# Get model object
model = result.get('model')
if model and hasattr(model, '__dict__'):
    d = model.__dict__
    
    # Print YAML config
    if 'yaml' in d:
        yaml_cfg = d['yaml']
        print("=" * 80)
        print("MODEL YAML ARCHITECTURE CONFIG")
        print("=" * 80)
        if isinstance(yaml_cfg, dict):
            import json
            
            # Print structured
            print(f"\nnc (number of classes): {yaml_cfg.get('nc', '?')}")
            print(f"depth_multiple: {yaml_cfg.get('depth_multiple', '?')}")
            print(f"width_multiple: {yaml_cfg.get('width_multiple', '?')}")
            
            if 'backbone' in yaml_cfg:
                print(f"\n--- BACKBONE ---")
                for layer in yaml_cfg['backbone']:
                    print(f"  {layer}")
            
            if 'head' in yaml_cfg:
                print(f"\n--- HEAD ---")
                for layer in yaml_cfg['head']:
                    print(f"  {layer}")
            
            if 'scales' in yaml_cfg:
                print(f"\n--- SCALES ---")
                print(f"  {yaml_cfg['scales']}")
        else:
            print(yaml_cfg)
    
    # Print names
    if 'names' in d:
        print(f"\n--- CLASS NAMES ---")
        print(f"  {d['names']}")
    
    # Print nc
    if 'nc' in d:
        print(f"\n--- NUMBER OF CLASSES ---")
        print(f"  {d['nc']}")

    # Print all string/numeric attrs
    print(f"\n--- KEY MODEL ATTRIBUTES ---")
    for k, v in sorted(d.items()):
        if isinstance(v, (str, int, float, bool, type(None))):
            print(f"  {k} = {repr(v)}")

# Print training info
print(f"\n{'='*80}")
print("TRAINING CONFIGURATION")
print(f"{'='*80}")
train_args = result.get('train_args', {})
key_args = ['task', 'model', 'data', 'epochs', 'batch', 'imgsz', 'device', 
            'pretrained', 'optimizer', 'lr0', 'lrf', 'project', 'name']
for k in key_args:
    if k in train_args:
        print(f"  {k}: {train_args[k]}")

print(f"\n{'='*80}")
print("PERFORMANCE METRICS")
print(f"{'='*80}")
metrics = result.get('train_metrics', {})
for k, v in metrics.items():
    if isinstance(v, float):
        print(f"  {k}: {v:.5f}")
    else:
        print(f"  {k}: {v}")

# Print epoch info  
print(f"\n  epoch: {result.get('epoch', '?')}")
print(f"  best_fitness: {result.get('best_fitness', '?')}")
