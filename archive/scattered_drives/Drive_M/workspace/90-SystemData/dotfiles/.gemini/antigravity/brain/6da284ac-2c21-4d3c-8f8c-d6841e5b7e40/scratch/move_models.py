import os
import shutil

target_dir = r"M:\chakramodelpro\valid_models"
os.makedirs(target_dir, exist_ok=True)

source_dirs = [r"M:\chakramodel", r"M:\chakramodelpro"]

moved_count = 0

for d in source_dirs:
    for root, _, files in os.walk(d):
        if os.path.abspath(root) == os.path.abspath(target_dir):
            continue
            
        for f in files:
            if f.endswith('.pt'):
                src_path = os.path.join(root, f)
                dst_path = os.path.join(target_dir, f)
                
                if os.path.exists(dst_path):
                    # Collision resolution
                    parent_dir = os.path.basename(root)
                    base, ext = os.path.splitext(f)
                    new_name = f"{base}_{parent_dir}{ext}"
                    dst_path = os.path.join(target_dir, new_name)
                    
                    # If still collides, add random number
                    import uuid
                    if os.path.exists(dst_path):
                        new_name = f"{base}_{parent_dir}_{str(uuid.uuid4())[:4]}{ext}"
                        dst_path = os.path.join(target_dir, new_name)
                        
                shutil.move(src_path, dst_path)
                moved_count += 1
                print(f"Moved {src_path} -> {dst_path}")

print(f"Total moved: {moved_count}")
