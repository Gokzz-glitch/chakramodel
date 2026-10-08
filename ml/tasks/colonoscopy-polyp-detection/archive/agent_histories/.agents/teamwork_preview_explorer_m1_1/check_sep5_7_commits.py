import subprocess

commits = ['55c859b7', 'd5807305', '52d97853', 'b67bcb1a', '2cac63f7']

for c in commits:
    res = subprocess.run(['git', '--no-pager', 'show', '--name-only', '--oneline', c], capture_output=True, text=True)
    lines = res.stdout.strip().split('\n')
    header = lines[0]
    files = lines[1:]
    print(f"Commit: {header}")
    print(f"  Files ({len(files)}): {', '.join(files[:10])}")
    if len(files) > 10:
        print(f"  ... and {len(files)-10} more")
    print()
