import re
from pathlib import Path

def apply_unified_diff(original_text, diff_text):
    original_lines = original_text.splitlines()
    diff_lines = diff_text.splitlines()
    
    # Simple hunk-based patch applier
    out = []
    orig_idx = 0
    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]
        if line.startswith("@@"):
            # @@ -orig_start,orig_len +new_start,new_len @@
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not m:
                raise ValueError(f"Bad hunk line: {line}")
            orig_start = int(m.group(1))
            orig_len = int(m.group(2)) if m.group(2) is not None else 1
            
            # Copy lines from orig_idx up to orig_start - 1 (1-indexed)
            target_idx = orig_start - 1
            while orig_idx < target_idx:
                out.append(original_lines[orig_idx])
                orig_idx += 1
            
            i += 1
            # Process hunk lines
            while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                hunk_line = diff_lines[i]
                if hunk_line.startswith("+"):
                    out.append(hunk_line[1:])
                elif hunk_line.startswith("-"):
                    # skip orig line
                    orig_idx += 1
                elif hunk_line.startswith(" "):
                    out.append(hunk_line[1:])
                    orig_idx += 1
                elif hunk_line == "":
                    # empty line in hunk could be context
                    out.append("")
                    orig_idx += 1
                else:
                    break
                i += 1
        else:
            i += 1
            
    # Append any remaining lines
    while orig_idx < len(original_lines):
        out.append(original_lines[orig_idx])
        orig_idx += 1
        
    return "\n".join(out) + "\n"

orig_path = Path(r"M:\chakramodel\src\chakra_transformer\transformer_segmenter.py")
diff_path = Path(r"M:\chakramodel\.agents\reviewer_m1_2_g13\transformer_diff.txt")

orig_text = orig_path.read_text(encoding="utf-8")
diff_text = diff_path.read_text(encoding="utf-8")

patched = apply_unified_diff(orig_text, diff_text)
out_path = Path(r"M:\chakramodel\.agents\explorer_m3_1_g14\annotated_transformer.py")
out_path.write_text(patched, encoding="utf-8")

print(f"Original lines: {len(orig_text.splitlines())}")
print(f"Patched lines: {len(patched.splitlines())}")
print(f"Patched bytes: {len(patched.encode('utf-8'))}")
