import os
import json

brain_dir = r'C:\Users\imgk3\.gemini\antigravity\brain'
output_folder = r'm:\chakramodel\conversation_history'
output_file = os.path.join(output_folder, 'HISTORY.JSON')

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

all_history = {}
count = 0

print("Extracting conversations...")
for root, dirs, files in os.walk(brain_dir):
    if 'transcript.jsonl' in files:
        path_parts = root.split(os.sep)
        try:
            brain_index = path_parts.index('brain')
            convo_id = path_parts[brain_index + 1]
        except ValueError:
            convo_id = 'unknown_' + os.path.basename(root)

        file_path = os.path.join(root, 'transcript.jsonl')
        convo_data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            step = json.loads(line)
                            # To save space, let's keep only USER_INPUT and PLANNER_RESPONSE (the messages)
                            if step.get('type') in ('USER_INPUT', 'PLANNER_RESPONSE'):
                                convo_data.append({
                                    'type': step.get('type'),
                                    'content': step.get('content', ''),
                                    'tool_calls': step.get('tool_calls', []),
                                    'source': step.get('source', '')
                                })
                        except json.JSONDecodeError:
                            pass
            if convo_data:
                all_history[convo_id] = convo_data
                count += 1
        except Exception as e:
            print(f"Failed to read {file_path}: {e}")

print(f"Writing {count} conversations to {output_file}...")
with open(output_file, 'w', encoding='utf-8') as out_f:
    json.dump(all_history, out_f, indent=2)

print(f"Done! Saved history of {count} conversations to {output_file}")
