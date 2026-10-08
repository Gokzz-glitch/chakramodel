import os

p_gdrive = r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel'

print("Checking directories in Google Drive chakramodel:")
for d in ['src', 'data', 'video_testing', 'weights', 'checkpoints', 'scripts', 'tests', 'dataset_yolo', 'outputs', 'archive']:
    full = os.path.join(p_gdrive, d)
    exists = os.path.exists(full)
    cnt = sum(len(f) for _, _, f in os.walk(full)) if exists else 0
    print(f"  Gdrive {d:<20}: exists={exists}, files={cnt}")
