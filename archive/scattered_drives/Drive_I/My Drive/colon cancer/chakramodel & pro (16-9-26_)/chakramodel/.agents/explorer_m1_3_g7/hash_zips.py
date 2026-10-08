import zipfile
import hashlib
import os

def zip_hash(zip_path, internal_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        with z.open(internal_path) as f:
            h = hashlib.md5()
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
            return h.hexdigest()

workspace = "m:\\chakramodel"
print("chakramodel-weights.zip:")
for name in ['chakra_transformer_best.pth', 'best.pt', 'conformal_calibration.json']:
    zp = os.path.join(workspace, 'chakramodel-weights.zip')
    print(f"  {name}: {zip_hash(zp, name)}")

print("\nchakramodel_weights_PRIVATE.zip:")
for name in ['weights/chakra_transformer_best.pth', 'weights/chakra_transformer_best.pth.bak', 'weights/best.pt']:
    zp = os.path.join(workspace, 'chakramodel_weights_PRIVATE.zip')
    print(f"  {name}: {zip_hash(zp, name)}")
