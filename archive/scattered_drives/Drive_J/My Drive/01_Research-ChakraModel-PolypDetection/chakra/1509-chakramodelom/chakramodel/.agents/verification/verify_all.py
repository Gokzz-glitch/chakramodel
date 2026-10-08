import subprocess
import os

datasets = ["cvc-colondb", "cvc-clinicdb", "etis-larib", "kvasir-seg"]

for dataset in datasets:
    dataset_path = f"M:\\chakramodel\\data\\{dataset}"
    if not os.path.exists(dataset_path):
        print(f"Skipping {dataset}, path not found.")
        continue
    
    print(f"\n==============================================")
    print(f"Running zero-trust verification on {dataset}")
    print(f"==============================================\n")
    
    cmd = [
        "python", 
        "M:\\chakramodel\\.agents\\verification\\supervised_verification_harness.py",
        "--dataset-root", dataset_path,
        "--script", "M:\\chakramodel\\.agents\\verification\\verify_eval.py"
    ]
    
    env = os.environ.copy()
    env["DATASET_ROOT"] = dataset_path
    
    result = subprocess.run(cmd, text=True, env=env)
    if result.returncode != 0:
        print(f"Verification failed for {dataset}")
        
print("All verifications complete.")
