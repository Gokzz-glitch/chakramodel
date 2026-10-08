import os

p_root = r'D:\15-0926chakramodel versioncontrol\chakramodel'
p_nested = r'D:\15-0926chakramodel versioncontrol\chakramodel\chakramodel'

print("Checking directories in D root:")
for d in ['src', 'data', 'video_testing', 'weights', 'checkpoints', 'scripts', 'tests', 'dataset_yolo']:
    print(f"  Root {d}: {os.path.exists(os.path.join(p_root, d))}")

print("\nChecking directories in D nested chakramodel:")
for d in ['src', 'data', 'video_testing', 'weights', 'checkpoints', 'scripts', 'tests', 'dataset_yolo']:
    print(f"  Nested {d}: {os.path.exists(os.path.join(p_nested, d))}")
