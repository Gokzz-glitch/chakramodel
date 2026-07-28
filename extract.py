import zipfile
import os

zip_path = r'M:\chakramodel\colon_cancer_dataset.zip'
extract_path = r'M:\GOKZZ_4\NIT HACKATHIN\datasets'

with zipfile.ZipFile(zip_path, 'r') as z:
    for member in z.infolist():
        # Replace the problematic trailing space in the folder name
        filename = member.filename
        if 'fecal /' in filename:
            filename = filename.replace('fecal /', 'fecal/')
            
        target_path = os.path.join(extract_path, os.path.normpath(filename))
        
        # Create directories if needed
        if member.is_dir():
            os.makedirs(target_path, exist_ok=True)
            continue
            
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Read the file from zip and write it
        with open(target_path, 'wb') as f:
            f.write(z.read(member.filename))

print("Extraction complete.")
