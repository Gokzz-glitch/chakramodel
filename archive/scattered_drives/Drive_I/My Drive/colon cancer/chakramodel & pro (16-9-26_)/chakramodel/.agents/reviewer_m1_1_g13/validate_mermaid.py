import re

with open('docs/ARCHITECTURE_DEEP_DIVE.md', 'r', encoding='utf-8') as f:
    content = f.read()

mermaid_blocks = re.findall(r'```mermaid\s+(.*?)```', content, re.DOTALL)
print(f'Total Mermaid blocks found: {len(mermaid_blocks)}')

for i, block in enumerate(mermaid_blocks, 1):
    lines = block.strip().split('\n')
    print(f'\n--- Block {i} ({lines[0]}) --- ({len(lines)} lines)')
    
    # Check subgraph open/close parity
    subgraph_opens = sum(1 for l in lines if l.strip().startswith('subgraph '))
    subgraph_ends = sum(1 for l in lines if l.strip() == 'end')
    print(f'Subgraphs: {subgraph_opens} opens, {subgraph_ends} ends')
    if subgraph_opens != subgraph_ends:
        print(f'ERROR: Unbalanced subgraphs in Block {i}!')
    
    # Check for unclosed brackets/quotes
    for l_idx, l in enumerate(lines, 1):
        stripped = l.strip()
        if not stripped or stripped.startswith('%%') or stripped.startswith('flowchart') or stripped.startswith('subgraph') or stripped == 'end':
            continue
        
        # Check matching square brackets
        if stripped.count('[') != stripped.count(']'):
            print(f'Line {l_idx}: Unmatched [] -> {stripped}')
        if stripped.count('{"') != stripped.count('"}') and stripped.count('{') != stripped.count('}'):
            print(f'Line {l_idx}: Unmatched {{}} -> {stripped}')
        if stripped.count('("') != stripped.count('")') and stripped.count('(') != stripped.count(')'):
            print(f'Line {l_idx}: Unmatched () -> {stripped}')
