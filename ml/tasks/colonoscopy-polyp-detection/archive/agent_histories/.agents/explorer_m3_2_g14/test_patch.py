import re
import sys

def apply_patch(orig_lines, diff_lines):
    hunks = []
    current_hunk = None
    for line in diff_lines:
        if line.startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if m:
                if current_hunk:
                    hunks.append(current_hunk)
                orig_start = int(m.group(1))
                orig_len = int(m.group(2)) if m.group(2) else 1
                new_start = int(m.group(3))
                new_len = int(m.group(4)) if m.group(4) else 1
                current_hunk = {'orig_start': orig_start, 'orig_len': orig_len, 'lines': []}
        elif current_hunk is not None:
            current_hunk['lines'].append(line)
    if current_hunk:
        hunks.append(current_hunk)
    
    res = list(orig_lines)
    offset = 0
    for idx, h in enumerate(hunks):
        start = h['orig_start'] - 1 + offset
        old_lines = []
        new_lines = []
        for l in h['lines']:
            if l.startswith('-'):
                old_lines.append(l[1:])
            elif l.startswith('+'):
                new_lines.append(l[1:])
            elif l.startswith(' '):
                old_lines.append(l[1:])
                new_lines.append(l[1:])
        
        actual_old = res[start:start+len(old_lines)]
        if actual_old != old_lines:
            print(f"Hunk {idx} mismatch at orig line {h['orig_start']}:")
            print("Expected:", [l.rstrip() for l in old_lines[:3]])
            print("Actual:  ", [l.rstrip() for l in actual_old[:3]])
            return None
        res[start:start+len(old_lines)] = new_lines
        offset += len(new_lines) - len(old_lines)
    return ''.join(res)

diff_lines = open('.agents/reviewer_m1_2_g13/chakranet_exact_diff.txt', 'r', encoding='utf-8').readlines()
orig_lines = open('src/models/chakranet_segmenter.py', 'r', encoding='utf-8').readlines()

patched = apply_patch(orig_lines, diff_lines)
if patched:
    print("Clean patch success!")
    lines = patched.splitlines()
    print("Total patched lines:", len(lines))
    print("Total bytes:", len(patched.encode('utf-8')))
    try:
        compile(patched, '<string>', 'exec')
        print("Python Syntax: VALID")
    except Exception as e:
        print("Python Syntax ERROR:", e)

    # Check tags
    tags = {
        '[BODY]': patched.count('[BODY]'),
        '[NECK]': patched.count('[NECK]'),
        '[HEAD]': patched.count('[HEAD]'),
        '[DECODER]': patched.count('[DECODER]'),
    }
    print("Tag counts:", tags)

    # Check tensor shape comments
    shapes = re.findall(r'\[B,\s*[^\]]+\]', patched)
    print("Tensor shape count [B, ...]:", len(shapes))

    # Check comment density
    comment_lines = [l for l in lines if l.strip().startswith('#')]
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
    print(f"Comments: {len(comment_lines)}, Code: {len(code_lines)}, Ratio: {len(comment_lines)/len(code_lines):.2%}")
else:
    print("Patch application failed!")
