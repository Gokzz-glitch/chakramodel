import os, shutil, random

CHD = "$HOME/mnt/Downloads/CHD".replace("$HOME", os.path.expanduser("~"))
NOCHD = "$HOME/mnt/Downloads/Non_CHD".replace("$HOME", os.path.expanduser("~"))
OUT = "$HOME/mnt/Downloads/chd_dataset".replace("$HOME", os.path.expanduser("~"))

# Get remaining patients
nochd_patients = [d for d in os.listdir(NOCHD) if os.path.isdir(f"{NOCHD}/{d}")]
random.seed(42)
random.shuffle(nochd_patients)

# Split
n_train = int(len(nochd_patients) * 0.70)
n_valid = int(len(nochd_patients) * 0.10)

train_ps = nochd_patients[:n_train]
valid_ps = nochd_patients[n_train:n_train+n_valid]
test_ps = nochd_patients[n_train+n_valid:]

print(f"Copying remaining {len(nochd_patients)} Non-CHD patients...")
print(f"  Train: {len(train_ps)} | Valid: {len(valid_ps)} | Test: {len(test_ps)}")

# Copy train
for p in train_ps:
    for f in os.listdir(f"{NOCHD}/{p}"):
        if f.endswith('.png'):
            shutil.copy2(f"{NOCHD}/{p}/{f}", f"{OUT}/nonchd/images/train/")
print(f"✓ Train complete: {len(os.listdir(f'{OUT}/nonchd/images/train'))} images")

# Copy valid
for p in valid_ps:
    for f in os.listdir(f"{NOCHD}/{p}"):
        if f.endswith('.png'):
            shutil.copy2(f"{NOCHD}/{p}/{f}", f"{OUT}/nonchd/images/valid/")
print(f"✓ Valid complete: {len(os.listdir(f'{OUT}/nonchd/images/valid'))} images")

# Copy test
for p in test_ps:
    for f in os.listdir(f"{NOCHD}/{p}"):
        if f.endswith('.png'):
            shutil.copy2(f"{NOCHD}/{p}/{f}", f"{OUT}/nonchd/images/test/")
print(f"✓ Test complete: {len(os.listdir(f'{OUT}/nonchd/images/test'))} images")

print("\n✓ All files copied successfully!")
