import os

src_cp = r'M:\chakramodel\checkpoints'
tgt_cp = r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel\checkpoints'

print("M:\\chakramodel\\checkpoints:")
if os.path.exists(src_cp):
    for f in os.listdir(src_cp):
        fp = os.path.join(src_cp, f)
        print(f"  {f}: {os.path.getsize(fp) / (1024*1024):.2f} MB")
else:
    print("  Does not exist!")

print("I:\\...\\checkpoints:")
if os.path.exists(tgt_cp):
    print(f"  Items: {os.listdir(tgt_cp)}")
else:
    print("  Does not exist!")
