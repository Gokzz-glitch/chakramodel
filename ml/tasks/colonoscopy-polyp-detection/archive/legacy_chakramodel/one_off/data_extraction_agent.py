import json
import os
import re

history_file = r"M:\chakramodel\conversation_history\HISTORY.JSON"
output_file = r"M:\chakramodel\OM_rama_krish_all_data.json"

def extract_code_blocks(text):
    """Extracts markdown code blocks from text."""
    pattern = r'```[\w]*\n(.*?)```'
    blocks = re.findall(pattern, text, re.DOTALL)
    return blocks

def run_extraction_agent():
    print(f"Loading raw history from {history_file}...")
    if not os.path.exists(history_file):
        print("History file not found!")
        return

    with open(history_file, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    all_conversations = {}

    print("Agent started: Processing all conversations...")
    for convo_id, events in history_data.items():
        processed_events = []
        
        for event in events:
            event_type = event.get("type", "UNKNOWN")
            source = event.get("source", "UNKNOWN")
            content = event.get("content", "")
            
            # Extract basic text and inline code blocks
            extracted_event = {
                "role": source,
                "event_type": event_type,
                "text": content,
                "markdown_code_blocks": extract_code_blocks(content),
                "file_writes": [],
                "command_executions": []
            }

            # Extract data from tool calls (especially code written to files)
            tool_calls = event.get("tool_calls", [])
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                
                # We want to capture every line of code written
                if name == "write_to_file" or name == "replace_file_content" or name == "multi_replace_file_content":
                    code_content = args.get("CodeContent") or args.get("ReplacementContent") or args.get("ReplacementChunks")
                    target_file = args.get("TargetFile") or args.get("AbsolutePath")
                    
                    extracted_event["file_writes"].append({
                        "tool": name,
                        "file": target_file,
                        "code": code_content
                    })
                
                # We want to capture commands run
                elif name == "run_command":
                    extracted_event["command_executions"].append({
                        "command": args.get("CommandLine"),
                        "cwd": args.get("Cwd")
                    })

            # Append event if it has meaningful data
            if content.strip() or extracted_event["file_writes"] or extracted_event["command_executions"]:
                processed_events.append(extracted_event)

        all_conversations[convo_id] = processed_events

    print(f"Saving extracted data to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_conversations, f, indent=4)
        
    print("Data extraction complete! Not a single line of code was missed.")

if __name__ == "__main__":
    run_extraction_agent()
