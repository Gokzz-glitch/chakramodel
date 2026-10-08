import json
import os
import re

history_file = r"M:\chakramodel\conversation_history\HISTORY.JSON"
output_file = r"M:\chakramodel\conversation_summaries.json"

def clean_text(text):
    # Remove XML tags like <USER_REQUEST>, <ADDITIONAL_METADATA>, etc.
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def summarize_conversations():
    if not os.path.exists(history_file):
        print(f"Error: {history_file} not found.")
        return

    with open(history_file, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    summaries = []

    for convo_id, events in history_data.items():
        summary = "No user input found."
        
        # Look for the first USER_INPUT
        for event in events:
            if event.get("type") == "USER_INPUT":
                content = event.get("content", "")
                
                # Extract just the <USER_REQUEST> part if present
                match = re.search(r'<USER_REQUEST>(.*?)</USER_REQUEST>', content, re.DOTALL)
                if match:
                    summary = match.group(1).strip()
                else:
                    summary = clean_text(content)
                    
                # Truncate summary if it's too long
                if len(summary) > 500:
                    summary = summary[:497] + "..."
                break
                
        summaries.append({
            "conversation_id": convo_id,
            "summary": summary
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=4)

    print(f"Successfully summarized {len(summaries)} conversations into {output_file}")

if __name__ == "__main__":
    summarize_conversations()
