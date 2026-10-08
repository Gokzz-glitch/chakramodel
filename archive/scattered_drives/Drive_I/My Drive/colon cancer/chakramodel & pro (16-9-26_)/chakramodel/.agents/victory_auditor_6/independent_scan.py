import os
import re
import sys

def main():
    files = ['paper/main.tex', 'docs/paper/ChakraModel_Final_Paper.md']
    banned = ['SOTA', 'State of the Art', 'State-of-the-Art', '0.9852', '0.9412', '0.8650']
    target = '0.8131'

    print("==================================================")
    print("INDEPENDENT VICTORY AUDITOR PROGRAMMATIC VERIFICATION")
    print("==================================================")

    total_violations = 0

    for file_path in files:
        if not os.path.exists(file_path):
            print(f"[FAIL] Missing file: {file_path}")
            total_violations += 1
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"\nScanning: {file_path} ({len(content)} chars, {len(content.splitlines())} lines)")
        
        # Banned scans
        for b in banned:
            matches = list(re.finditer(re.escape(b), content, re.IGNORECASE))
            if len(matches) > 0:
                print(f"  [VIOLATION] Found {len(matches)} occurrence(s) of banned string '{b}':")
                for m in matches:
                    line_no = content[:m.start()].count('\n') + 1
                    snippet = content[max(0, m.start()-40):min(len(content), m.end()+40)].replace('\n', ' ')
                    print(f"    Line {line_no}: ...{snippet}...")
                total_violations += len(matches)
            else:
                print(f"  [PASS] Zero occurrences of banned string '{b}'")

        # Target scan
        target_matches = list(re.finditer(re.escape(target), content))
        if len(target_matches) == 0:
            print(f"  [VIOLATION] Target string '{target}' NOT found in {file_path}")
            total_violations += 1
        else:
            print(f"  [PASS] Found {len(target_matches)} occurrence(s) of target string '{target}'")
            for m in target_matches[:3]:
                line_no = content[:m.start()].count('\n') + 1
                snippet = content[max(0, m.start()-30):min(len(content), m.end()+30)].replace('\n', ' ')
                print(f"    Line {line_no}: ...{snippet}...")

    print("\n==================================================")
    if total_violations == 0:
        print("[SUMMARY] ALL PROGRAMMATIC ACCEPTANCE CRITERIA PASSED (0 violations)")
        return 0
    else:
        print(f"[SUMMARY] PROGRAMMATIC ACCEPTANCE CRITERIA FAILED ({total_violations} violations)")
        return 1

if __name__ == '__main__':
    sys.exit(main())
