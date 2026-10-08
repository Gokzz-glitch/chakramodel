import zipfile
import os
import shutil
import sys

def extract_safely(zip_path, extract_dir):
    print(f"Extracting {zip_path} to {extract_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            # Clean the filename to remove trailing spaces in directory names
            # because Windows cannot handle folders named like 'fecal '
            parts = member.filename.replace('\\', '/').split('/')
            cleaned_parts = [p.strip() for p in parts]
            cleaned_filename = '/'.join(cleaned_parts)
            
            target_path = os.path.join(extract_dir, os.path.normpath(cleaned_filename))
            
            if member.is_dir() or target_path.endswith('\\') or target_path.endswith('/'):
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)
    print("Extraction complete.")

if __name__ == "__main__":
    zip_path = r"M:\chakramodel\colon_cancer_dataset.zip"
    extract_path = r"M:\chakramodel\data"
    extract_safely(zip_path, extract_path)
