import subprocess

commits = ['9450fb98', '6bae8d1c', 'c838cf3c', '4561228c', '3dedc11c', '106443cc', '3ba62e8d']

for c in commits:
    res = subprocess.run(['git', '--no-pager', 'show', '--name-only', '--oneline', c], capture_output=True, text=True)
    lines = res.stdout.strip().split('\n')
    header = lines[0]
    files = lines[1:]
    print(f"Commit: {header}")
    print(f"  Files ({len(files)}): {', '.join(files[:8])}")
    if len(files) > 8:
        print(f"  ... and {len(files)-8} more")
    print()
