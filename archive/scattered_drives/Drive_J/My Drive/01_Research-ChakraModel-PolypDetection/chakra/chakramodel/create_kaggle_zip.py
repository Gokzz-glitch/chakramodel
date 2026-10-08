import zipfile
import os

def create_kaggle_zip():
    print("Creating ChakraModel_Kaggle_Code.zip with Kaggle-safe forward slashes...")
    with zipfile.ZipFile('ChakraModel_Kaggle_Code.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Zip the src directory
        for root, dirs, files in os.walk('src'):
            for file in files:
                # Ensure we only include python files or relevant scripts (optional, but good practice)
                if file.endswith('.py') or file.endswith('.json') or file.endswith('.txt'):
                    file_path = os.path.join(root, file)
                    # Kaggle requires forward slashes for internal paths
                    arcname = file_path.replace("\\", "/")
                    zipf.write(file_path, arcname)
                    
        # Add requirements.txt
        if os.path.exists('requirements.txt'):
            zipf.write('requirements.txt', 'requirements.txt')
            
    print("Zip creation complete!")

if __name__ == "__main__":
    create_kaggle_zip()
