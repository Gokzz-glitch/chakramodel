import json
import os
import re

history_file = r"M:\chakramodel\conversation_history\HISTORY.JSON"
output_md = r"M:\chakramodel\OM_rama_krish_convo.md"
output_json = r"M:\chakramodel\OM_rama_krish_convo.json"

def clean_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def extract_time_and_summary():
    if not os.path.exists(history_file):
        print(f"Error: {history_file} not found.")
        return

    with open(history_file, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    results = []

    for convo_id, events in history_data.items():
        summary = "No user input found."
        timestamp = "Unknown timestamp"
        
        for event in events:
            if event.get("type") == "USER_INPUT":
                content = event.get("content", "")
                
                # Extract timestamp
                time_match = re.search(r'The current local time is:\s*([^\.]+)', content)
                if time_match:
                    timestamp = time_match.group(1).strip()
                
                # Extract summary
                req_match = re.search(r'<USER_REQUEST>(.*?)</USER_REQUEST>', content, re.DOTALL)
                if req_match:
                    summary = req_match.group(1).strip()
                else:
                    # Remove the metadata part for summary
                    content_no_metadata = re.sub(r'<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>', '', content, flags=re.DOTALL)
                    summary = clean_text(content_no_metadata)
                    
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                break
                
        results.append({
            "timestamp": timestamp,
            "conversation_id": convo_id,
            "summary": summary
        })

    # Sort by timestamp (as strings, ISO 8601 sorts well alphabetically)
    results.sort(key=lambda x: x["timestamp"])

    # Write to JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    # Write to Markdown
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# OM_rama_krish_convo\n\n")
        f.write("List of all conversations with timestamps:\n\n")
        for res in results:
            f.write(f"- **{res['timestamp']}** | ID: `{res['conversation_id']}`\n")
            f.write(f"  - *Request*: {res['summary'].replace(chr(10), ' ')}\n")

    print(f"Successfully processed {len(results)} conversations.")
    print(f"Outputs written to {output_md} and {output_json}")

if __name__ == "__main__":
    extract_time_and_summary()
