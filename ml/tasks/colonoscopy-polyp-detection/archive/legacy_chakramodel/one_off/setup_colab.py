import os
import shutil
import sys

def main():
    src_base = os.path.dirname(os.path.abspath(__file__))
    
    if len(sys.argv) > 1:
        dest_base = sys.argv[1]
    else:
        # Default destination fallback if not provided
        if os.path.exists(r'J:\My Drive'):
            dest_base = r'J:\My Drive\chakramodel'
        else:
            dest_base = os.path.join(os.path.expanduser("~"), "Google Drive", "chakramodel")
            
    print(f"Source: {src_base}")
    print(f"Destination: {dest_base}")
    
    os.makedirs(dest_base, exist_ok=True)
    
    print('Copying src...')
    dest_src = os.path.join(dest_base, 'src')
    if os.path.exists(dest_src):
        shutil.rmtree(dest_src)
    shutil.copytree(os.path.join(src_base, 'src'), dest_src)
    
    metrics_src = os.path.join(src_base, 'metrics_engine_v2.py')
    if os.path.exists(metrics_src):
        shutil.copy2(metrics_src, os.path.join(dest_src, 'metrics_engine_v2.py'))
    
    print('Copying weights...')
    dest_weights = os.path.join(dest_base, 'weights')
    if os.path.exists(dest_weights):
        shutil.rmtree(dest_weights)
    shutil.copytree(os.path.join(src_base, 'weights'), dest_weights)
    
    print('Copying data...')
    os.makedirs(os.path.join(dest_base, 'data'), exist_ok=True)
    
    dest_colondb = os.path.join(dest_base, 'data', 'cvc-colondb')
    if os.path.exists(dest_colondb):
        shutil.rmtree(dest_colondb)
    shutil.copytree(os.path.join(src_base, 'data', 'cvc-colondb'), dest_colondb)
    
    dest_cvc300 = os.path.join(dest_base, 'data', 'cvc-300')
    if os.path.exists(dest_cvc300):
        shutil.rmtree(dest_cvc300)
    shutil.copytree(os.path.join(src_base, 'data', 'cvc-300'), dest_cvc300)
    
    print('Copying robust notebook...')
    nb_src = os.path.join(src_base, 'Colab_GPU_Fast_Verify.ipynb')
    if os.path.exists(nb_src):
        shutil.copy2(nb_src, dest_base)
    
    print('Copy completed successfully.')

if __name__ == '__main__':
    main()
