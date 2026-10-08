"""Inspect the chakra_transformer_best weight checkpoint pickle."""
import zipfile
import pickle
import io

zip_path = r'C:\Users\imgk3\Downloads\chakra_transformer_best (2).zip'

with zipfile.ZipFile(zip_path, 'r') as zf:
    entries = zf.infolist()
    print(f"Total entries: {len(entries)}")
    
    # Find pkl file
    pkl_files = [e for e in entries if e.filename.endswith('.pkl')]
    print(f"Pickle files: {[e.filename for e in pkl_files]}")
    
    # Read version/format
    for name in ['chakra_transformer_best/byteorder', 'chakra_transformer_best/.format_version']:
        try:
            print(f"{name}: {zf.read(name).decode().strip()}")
        except:
            pass
    
    pkl_data = zf.read(pkl_files[0].filename)
    print(f"Pickle size: {len(pkl_data):,} bytes")
    
    # Total data size
    data_files = [e for e in entries if '/data/' in e.filename]
    total_bytes = sum(e.file_size for e in data_files)
    print(f"Total tensor data: {total_bytes:,} bytes ({total_bytes/1024/1024:.2f} MB)")
    print(f"Number of tensor files: {len(data_files)}")

# Parse pickle
class InspectorUnpickler(pickle.Unpickler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_refs = []
    
    def find_class(self, module, name):
        self.class_refs.append(f"{module}.{name}")
        if module == 'collections' and name == 'OrderedDict':
            from collections import OrderedDict
            return OrderedDict
        if '_rebuild' in name:
            def dummy(*a, **kw):
                # Try to extract shape info
                if len(a) > 1 and isinstance(a[1], tuple):
                    return f"<TENSOR:shape={a[1]}>"
                return "<TENSOR>"
            return dummy
        if 'Storage' in name or 'storage' in module:
            class S:
                def __init__(self, *a, **kw): pass
                def __setstate__(self, s): pass
            return S
        class D:
            _mod = module
            _nm = name
            def __init__(self, *a, **kw):
                self._args = a
                self._kwargs = kw
            def __setstate__(self, state):
                if isinstance(state, dict):
                    self.__dict__.update(state)
            def __repr__(self):
                return f"<{module}.{name}>"
        D.__name__ = name
        D.__module__ = module
        return D
    
    def persistent_load(self, pid):
        return f"<STORAGE:{pid}>"

unpickler = InspectorUnpickler(io.BytesIO(pkl_data))
result = unpickler.load()

# Print unique class references
print(f"\n{'='*80}")
print("CLASS REFERENCES IN PICKLE")
print(f"{'='*80}")
seen = set()
for ref in unpickler.class_refs:
    if ref not in seen:
        print(f"  {ref}")
        seen.add(ref)

# Analyze checkpoint structure
print(f"\n{'='*80}")
print("CHECKPOINT STRUCTURE")
print(f"{'='*80}")

if isinstance(result, dict):
    print(f"Type: dict with {len(result)} keys")
    for k, v in result.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            print(f"  [{k}]: {repr(v)}")
        elif isinstance(v, dict):
            print(f"  [{k}]: dict ({len(v)} keys)")
        elif isinstance(v, (list, tuple)):
            print(f"  [{k}]: {type(v).__name__} ({len(v)} items)")
        else:
            print(f"  [{k}]: {type(v).__module__}.{type(v).__name__}")
    
    # Print state_dict keys to understand architecture
    for sd_key in ['model_state_dict', 'state_dict', 'student_state_dict', 'model']:
        if sd_key in result and isinstance(result[sd_key], dict):
            sd = result[sd_key]
            print(f"\n{'='*80}")
            print(f"STATE DICT: '{sd_key}' ({len(sd)} keys)")
            print(f"{'='*80}")
            for k, v in list(sd.items()):
                print(f"  {k}: {v}")
            break
    
    # Print other metadata
    for meta_key in ['config', 'cfg', 'args', 'hyperparameters', 'hparams', 'epoch', 'best_metric', 'best_dice', 'best_loss']:
        if meta_key in result:
            val = result[meta_key]
            print(f"\n--- {meta_key} ---")
            if isinstance(val, dict):
                for mk, mv in val.items():
                    print(f"    {mk}: {mv}")
            else:
                print(f"    {val}")

elif isinstance(result, (dict,)):
    # It's a plain state dict
    print(f"Plain state dict with {len(result)} keys")
    for k, v in list(result.items())[:50]:
        print(f"  {k}: {v}")
else:
    print(f"Result type: {type(result)}")
    if hasattr(result, '__dict__'):
        for k, v in result.__dict__.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                print(f"  .{k} = {repr(v)}")

print(f"\n{'='*80}")
print("DONE")
