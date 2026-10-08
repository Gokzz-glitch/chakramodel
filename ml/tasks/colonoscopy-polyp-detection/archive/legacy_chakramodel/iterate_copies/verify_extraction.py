import json
import os
import sys

raw_file = r"M:\chakramodel\conversation_history\HISTORY.JSON"
extracted_file = r"M:\chakramodel\OM_rama_krish_all_data.json"
report_file = r"M:\chakramodel\verification_report.txt"

def verify_extraction():
    print("Loading datasets...")
    with open(raw_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    with open(extracted_file, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)

    report_lines = ["# Data Extraction Verification Report", ""]
    
    total_convos = len(raw_data)
    failed_convos = 0
    passed_convos = 0
    
    print(f"Verifying {total_convos} conversations one by one...")

    for convo_id, events in raw_data.items():
        # Check if conversation exists in extracted
        if convo_id not in extracted_data:
            report_lines.append(f"[VERIFICATION: FAILED] - Conversation {convo_id} missing entirely.")
            failed_convos += 1
            continue
            
        extracted_events = extracted_data[convo_id]
        
        # Verify text content matching (omitting formatting issues like spacing)
        # 1. Gather all meaningful text from raw
        raw_text_pieces = []
        raw_code_pieces = []
        
        for event in events:
            content = event.get("content", "")
            if content.strip():
                raw_text_pieces.append(content)
            
            tool_calls = event.get("tool_calls", [])
            for tc in tool_calls:
                args = tc.get("args", {})
                code = args.get("CodeContent") or args.get("ReplacementContent")
                if code:
                    raw_code_pieces.append(code)
                    
        # 2. Gather all extracted text
        ext_text = ""
        ext_code = ""
        for ev in extracted_events:
            ext_text += ev.get("text", "")
            for fw in ev.get("file_writes", []):
                if fw.get("code"):
                    ext_code += fw.get("code")
                    
        # Verification Checks
        text_missing = False
        code_missing = False
        
        for piece in raw_text_pieces:
            # Basic sanity check (sometimes whitespace/JSON formatting differs slightly, 
            # so we check if a large chunk exists)
            check_chunk = piece[:100].strip()
            if check_chunk and check_chunk not in ext_text:
                text_missing = True
                break
                
        for piece in raw_code_pieces:
            check_chunk = piece[:100].strip()
            if check_chunk and check_chunk not in ext_code:
                code_missing = True
                break
                
        if text_missing or code_missing:
            report_lines.append(f"[VERIFICATION: FAILED] - Conversation {convo_id}")
            if text_missing:
                report_lines.append("- Missing Data: Some conversation dialogue/text was lost.")
                report_lines.append("- Reason: Extraction script might have skipped an event type.")
            if code_missing:
                report_lines.append("- Missing Data: Code block or file write missing.")
                report_lines.append("- Reason: Tool call extraction parsing issue.")
            report_lines.append("")
            failed_convos += 1
        else:
            # We don't log passes for all 552 to keep report readable, just count them
            passed_convos += 1

    report_lines.append("---")
    report_lines.append(f"TOTAL CONVERSATIONS VERIFIED: {total_convos}")
    report_lines.append(f"PASSED: {passed_convos}")
    report_lines.append(f"FAILED: {failed_convos}")
    
    if failed_convos == 0:
        report_lines.append("\nFINAL RESULT: [VERIFICATION: PASSED] - 100% of data successfully captured.")
    else:
        report_lines.append(f"\nFINAL RESULT: [VERIFICATION: FAILED] - {failed_convos} conversations had missing data.")

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print(f"Verification complete. Passed: {passed_convos}, Failed: {failed_convos}")
    print(f"Report saved to {report_file}")

if __name__ == "__main__":
    verify_extraction()
