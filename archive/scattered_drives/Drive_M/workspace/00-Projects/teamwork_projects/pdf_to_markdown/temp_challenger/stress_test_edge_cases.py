import subprocess
import sys
import json
import os
import shutil

def run_cmd(args):
    cmd = [sys.executable, "verify_conversion.py"] + args
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return res.returncode, res.stdout, res.stderr

def stress_test():
    os.makedirs("temp_challenger/edge_cases", exist_ok=True)
    results = {}

    print("=== STRESS TESTING EDGE CASES IN verify_conversion.py ===")

    # 1. Empty Markdown file
    empty_md = "temp_challenger/edge_cases/empty.md"
    with open(empty_md, "w", encoding="utf-8") as f:
        f.write("")
    ret, out, err = run_cmd(["--md", empty_md, "--report", "temp_challenger/edge_cases/rep_empty_md.json", "--offline"])
    results["empty_markdown"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"1. Empty Markdown: ExitCode={ret}")

    # 2. Empty Source JSON file
    empty_json = "temp_challenger/edge_cases/empty.json"
    with open(empty_json, "w", encoding="utf-8") as f:
        f.write("")
    ret, out, err = run_cmd(["--source", empty_json, "--report", "temp_challenger/edge_cases/rep_empty_json.json", "--offline"])
    results["empty_source_json"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"2. Empty Source JSON: ExitCode={ret}")

    # 3. Corrupt Source JSON file (syntax error / malformed)
    corrupt_json = "temp_challenger/edge_cases/corrupt.json"
    with open(corrupt_json, "w", encoding="utf-8") as f:
        f.write("{'bad_json': truncated...[1, 2,")
    ret, out, err = run_cmd(["--source", corrupt_json, "--report", "temp_challenger/edge_cases/rep_corrupt_json.json", "--offline"])
    results["corrupt_source_json"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"3. Corrupt Source JSON: ExitCode={ret}")

    # 4. Missing --report argument (should use default)
    # To test without overwriting real verification_report.json, let's backup real verification_report.json first
    shutil.copy("verification_report.json", "temp_challenger/edge_cases/real_rep_backup.json")
    ret, out, err = run_cmd(["--offline"])
    results["default_args_real_files"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"4. Missing --report argument (default path): ExitCode={ret}")

    # 5. Invalid report destination path (directory does not exist)
    bad_report_path = "temp_challenger/edge_cases/non_existent_subdir/report.json"
    ret, out, err = run_cmd(["--report", bad_report_path, "--offline"])
    results["invalid_report_dir"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"5. Invalid report directory: ExitCode={ret}")

    # 6. Non-existent markdown file
    ret, out, err = run_cmd(["--md", "non_existent_file.md", "--offline"])
    results["non_existent_md"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"6. Non-existent Markdown: ExitCode={ret}")

    # 7. Non-existent source JSON file
    ret, out, err = run_cmd(["--source", "non_existent_source.json", "--offline"])
    results["non_existent_source"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"7. Non-existent Source JSON: ExitCode={ret}")

    # 8. Markdown without Page Anchors (<!-- Page N -->)
    no_anchor_md = "temp_challenger/edge_cases/no_anchors.md"
    with open("Opus1.md", "r", encoding="utf-8") as f:
        md_text = f.read()
    import re
    stripped_md = re.sub(r'<!-- Page \d+ -->\n?', '', md_text)
    with open(no_anchor_md, "w", encoding="utf-8") as f:
        f.write(stripped_md)
    ret, out, err = run_cmd(["--md", no_anchor_md, "--report", "temp_challenger/edge_cases/rep_no_anchors.json", "--offline"])
    results["markdown_without_page_anchors"] = {
        "exit_code": ret,
        "stdout_snippet": out.strip()[-300:] if out else "",
        "stderr_snippet": err.strip()[-300:] if err else ""
    }
    print(f"8. Markdown without Page Anchors: ExitCode={ret}")

    # Save summary of stress test
    with open("temp_challenger/stress_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nDetailed results saved to temp_challenger/stress_test_results.json")

if __name__ == "__main__":
    stress_test()
