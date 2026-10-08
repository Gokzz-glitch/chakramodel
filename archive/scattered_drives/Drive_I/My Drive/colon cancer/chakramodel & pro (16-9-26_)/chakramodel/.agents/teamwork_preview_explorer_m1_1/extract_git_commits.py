import subprocess
import json

cmd = ['git', '--no-pager', 'log', '--reverse', '--pretty=format:%H|%h|%ad|%an|%ae|%s', '--date=iso']
res = subprocess.run(cmd, capture_output=True, text=True, check=True)
lines = res.stdout.strip().split('\n')

commits = []
for l in lines:
    parts = l.split('|')
    full_hash, short_hash, ad, an, ae, s = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
    
    # Get stat with --no-pager
    stat_res = subprocess.run(['git', '--no-pager', 'show', '--stat', '--oneline', short_hash], capture_output=True, text=True)
    stat_lines = stat_res.stdout.split('\n')
    stat_summary = stat_lines[-2] if len(stat_lines) > 2 else ''
    files_changed = [line.strip() for line in stat_lines[1:-2] if '|' in line][:10]
    
    commits.append({
        'hash': full_hash,
        'short_hash': short_hash,
        'date': ad,
        'author': an,
        'email': ae,
        'subject': s,
        'summary': stat_summary.strip(),
        'sample_files': files_changed
    })

with open('.agents/teamwork_preview_explorer_m1_1/git_commits_detailed.json', 'w', encoding='utf-8') as f:
    json.dump(commits, f, indent=2)

print(f"Successfully extracted {len(commits)} commits:")
for c in commits:
    print(f"[{c['date']}] {c['short_hash']} | {c['author']} | {c['subject']} ({c['summary']})")
