import os
import subprocess

def main():
    print("Starting Combo 4...")
    with open("combo4.log", "w") as f4:
        subprocess.run(["python", "-u", "notebooks/Combo4_DiffusionAug_ChakraNet.py"], stdout=f4, stderr=subprocess.STDOUT)
    print("Combo 4 done. Starting Combo 6...")
    with open("combo6.log", "w") as f6:
        subprocess.run(["python", "-u", "notebooks/Combo6_ChakraTransformer.py"], stdout=f6, stderr=subprocess.STDOUT)
    print("Combo 6 done.")

if __name__ == "__main__":
    main()
