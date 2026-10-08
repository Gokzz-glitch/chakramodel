import zipfile
import io
import pickle

class SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "torch._utils" and name == "_rebuild_tensor_v2":
            return lambda *args: ("tensor", args)
        if module == "collections" and name == "OrderedDict":
            return dict
        if module == "torch" and name in ("FloatStorage", "LongStorage", "IntStorage", "HalfStorage"):
            return lambda *args: ("storage", args)
        # return dummy
        return lambda *args: (module, name, args)

def check_keys():
    print("Checking chakra_transformer_best.pth.bak...")
    with zipfile.ZipFile(r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\chakramodel_weights_PRIVATE.zip") as outer_zip:
        bak_bytes = outer_zip.read("weights/chakra_transformer_best.pth.bak")
        print(f"Read {len(bak_bytes):,} bytes.")
        
        # Check if bak_bytes is a zip
        inner_bio = io.BytesIO(bak_bytes)
        if zipfile.is_zipfile(inner_bio):
            with zipfile.ZipFile(inner_bio) as inner_zip:
                print("Inner zip contents:", inner_zip.namelist()[:10])
                pkl_name = [n for n in inner_zip.namelist() if n.endswith("data.pkl")][0]
                pkl_data = inner_zip.read(pkl_name)
                state_dict = SafeUnpickler(io.BytesIO(pkl_data)).load()
                keys = list(state_dict.keys()) if isinstance(state_dict, dict) else []
                print(f"Total keys: {len(keys)}")
                print(f"First 10 keys: {keys[:10]}")
                module_keys = [k for k in keys if k.startswith("module.")]
                print(f"Keys starting with 'module.': {len(module_keys)}")
        else:
            print("Not a zipfile, might be legacy pickle.")

if __name__ == "__main__":
    check_keys()
