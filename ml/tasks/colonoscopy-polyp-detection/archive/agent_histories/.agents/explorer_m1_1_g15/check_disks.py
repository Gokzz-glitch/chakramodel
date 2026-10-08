import os

print("=== Drive Space Status ===")
for d in ['C:\\', 'D:\\', 'I:\\', 'M:\\']:
    try:
        import shutil
        total, used, free = shutil.disk_usage(d)
        print(f"Drive {d}: Total: {total/(1024**3):.2f} GB | Used: {used/(1024**3):.2f} GB | Free: {free/(1024**3):.2f} GB")
    except Exception as e:
        print(f"Drive {d}: Error {e}")
