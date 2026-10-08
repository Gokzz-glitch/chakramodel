"""
Inspect a PyTorch model checkpoint without importing torch.
We parse the pickle file directly and the zip archive to extract metadata.
"""
import zipfile
import pickle
import io
import struct
import sys
import os

zip_path = r'C:\Users\imgk3\Downloads\best.zip'

print("=" * 80)
print("MODEL WEIGHT INSPECTION (No-Torch Mode)")
print("=" * 80)

# First, inspect the zip archive structure
print("\n--- ZIP ARCHIVE STRUCTURE ---")
with zipfile.ZipFile(zip_path, 'r') as zf:
    for info in zf.infolist():
        print(f"  {info.filename}  ({info.file_size:,} bytes)")
    
    # Read version
    if 'best/version' in [i.filename for i in zf.infolist()]:
        version = zf.read('best/version').decode().strip()
        print(f"\n  PyTorch serialization version: {version}")
    
    # Read data.pkl
    pkl_data = zf.read('best/data.pkl')
    print(f"  Pickle data size: {len(pkl_data):,} bytes")

# Now parse the pickle using a custom unpickler that records class references
print("\n--- PICKLE CLASS REFERENCES ---")

class InspectorUnpickler(pickle.Unpickler):
    """Custom unpickler that records all GLOBAL/STACK_GLOBAL references."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_refs = []
        self.rebuild_calls = []
    
    def find_class(self, module, name):
        self.class_refs.append(f"{module}.{name}")
        
        # Return dummy classes for known torch types
        if module == 'collections' and name == 'OrderedDict':
            from collections import OrderedDict
            return OrderedDict
        
        # For torch._utils._rebuild_tensor_v2 and similar
        if '_rebuild' in name:
            self.rebuild_calls.append(f"{module}.{name}")
            def dummy_rebuild(*args, **kwargs):
                return f"<TENSOR:{args[1] if len(args) > 1 else '?'}>"
            return dummy_rebuild
        
        # For torch.storage types
        if 'Storage' in name or 'storage' in module:
            class DummyStorage:
                def __init__(self, *args, **kwargs):
                    pass
                def __setstate__(self, state):
                    pass
            return DummyStorage
        
        # For model classes - create dummy
        class DummyClass:
            _recorded_module = module
            _recorded_name = name
            def __init__(self, *args, **kwargs):
                self._init_args = args
                self._init_kwargs = kwargs
            def __setstate__(self, state):
                if isinstance(state, dict):
                    self.__dict__.update(state)
            def __reduce_ex__(self, protocol):
                return (type(self), ())
            def __repr__(self):
                return f"<{module}.{name}>"
        
        DummyClass.__name__ = name
        DummyClass.__module__ = module
        return DummyClass
    
    def persistent_load(self, pid):
        # Handle persistent IDs (used for tensor storage references)
        return f"<STORAGE:{pid}>"

try:
    unpickler = InspectorUnpickler(io.BytesIO(pkl_data))
    result = unpickler.load()
    
    # Print discovered classes
    seen = set()
    for ref in unpickler.class_refs:
        if ref not in seen:
            print(f"  {ref}")
            seen.add(ref)
    
    print(f"\n--- CHECKPOINT STRUCTURE ---")
    if isinstance(result, dict):
        print(f"  Type: dict with {len(result)} keys")
        for k, v in result.items():
            if isinstance(v, dict):
                print(f"  [{k}]: dict ({len(v)} entries)")
                # Print dict contents for small dicts or metadata dicts
                if k in ['train_args', 'overrides', 'args'] or (isinstance(v, dict) and len(v) < 30):
                    for mk, mv in v.items():
                        if isinstance(mv, (str, int, float, bool, type(None))):
                            print(f"      {mk}: {mv}")
                        elif isinstance(mv, dict) and len(mv) < 10:
                            print(f"      {mk}: {mv}")
                        else:
                            print(f"      {mk}: {type(mv).__name__}")
            elif isinstance(v, (str, int, float, bool, type(None))):
                print(f"  [{k}]: {repr(v)}")
            elif isinstance(v, (list, tuple)):
                print(f"  [{k}]: {type(v).__name__} ({len(v)} items)")
            else:
                type_info = type(v)
                print(f"  [{k}]: {getattr(type_info, '__module__', '?')}.{getattr(type_info, '__name__', '?')}")
                
                # Introspect model objects
                if k in ['model', 'ema'] and hasattr(v, '__dict__'):
                    obj_dict = v.__dict__
                    for attr_name in ['yaml', 'yaml_file', 'names', 'nc', 'task', 'args', 
                                      'stride', 'inplace', 'pt_path', 'model_name',
                                      'overrides', 'cfg', 'ch']:
                        if attr_name in obj_dict:
                            val = obj_dict[attr_name]
                            if isinstance(val, (str, int, float, bool, type(None), list)):
                                print(f"      .{attr_name}: {val}")
                            elif isinstance(val, dict):
                                print(f"      .{attr_name}: dict({len(val)} keys)")
                                for yk, yv in val.items():
                                    if isinstance(yv, (str, int, float, bool, type(None))):
                                        print(f"          {yk}: {yv}")
                                    elif isinstance(yv, list):
                                        # Print YAML architecture list
                                        print(f"          {yk}:")
                                        for item in yv:
                                            print(f"            {item}")
                                    else:
                                        print(f"          {yk}: {type(yv).__name__}")
                    
                    # Print all attribute names
                    print(f"      --- all attributes ---")
                    for attr_name in sorted(obj_dict.keys()):
                        val = obj_dict[attr_name]
                        if isinstance(val, (str, int, float, bool, type(None))):
                            print(f"      .{attr_name} = {repr(val)}")

except Exception as e:
    print(f"\nError during pickle parsing: {e}")
    import traceback
    traceback.print_exc()

# Also try to find string patterns directly in binary
print("\n--- RAW BINARY STRING SEARCH ---")
search_terms = [b'yolov', b'YOLOv', b'ultralytics', b'Ultralytics', b'darknet', 
                b'detect', b'segment', b'classify', b'pose',
                b'backbone', b'nc:', b'depth_multiple', b'width_multiple',
                b'.yaml', b'train_args', b'best_fitness', b'epoch']

for term in search_terms:
    positions = []
    start = 0
    while True:
        idx = pkl_data.find(term, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    if positions:
        print(f"  '{term.decode()}' found {len(positions)} time(s)")
        for pos in positions[:3]:
            # Extract context
            ctx_start = max(0, pos - 20)
            ctx_end = min(len(pkl_data), pos + len(term) + 60)
            context = pkl_data[ctx_start:ctx_end]
            # Clean up non-printable chars
            clean = ''.join(chr(b) if 32 <= b < 127 else '.' for b in context)
            print(f"    @{pos}: ...{clean}...")

# Count tensor data files to estimate parameter count
print("\n--- TENSOR DATA FILES ---")
with zipfile.ZipFile(zip_path, 'r') as zf:
    data_files = [i for i in zf.infolist() if i.filename.startswith('best/data/')]
    total_data_bytes = sum(i.file_size for i in data_files)
    print(f"  Number of tensor files: {len(data_files)}")
    print(f"  Total tensor data: {total_data_bytes:,} bytes ({total_data_bytes/1024/1024:.2f} MB)")
    
    # Estimate parameters (assuming mostly float32 = 4 bytes or float16 = 2 bytes)
    print(f"  Estimated params (float32): {total_data_bytes // 4:,}")
    print(f"  Estimated params (float16): {total_data_bytes // 2:,}")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
