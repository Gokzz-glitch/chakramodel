import subprocess

commits = [
    '2f528801', '9842e360', 'cdfb78f9', 'e23e679a', '110c9f1d',
    '1fb12e8c', '2080d3df', 'a0e6f187', '0e8b5b87', '3a25fb67',
    '1e6b2ecd', 'fc5885b6', 'abc9a4e2'
]

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
