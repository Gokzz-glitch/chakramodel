import json
import sys

files = [
    r'C:\Users\imgk3\.gemini\antigravity\brain\16a7b52d-2026-4a39-a1f2-5913006fc61e\.system_generated\logs\transcript.jsonl',
    r'C:\Users\imgk3\.gemini\antigravity\brain\cef9f13d-2b54-4197-a20b-69e878ae6005\.system_generated\logs\transcript.jsonl'
]

keywords = ['false', 'score', 'layer', 'architect', 'adversarial', 'experiment', 'retrospective']

for f in files:
    print(f'\n--- {f} ---')
    try:
        with open(f, 'r', encoding='utf-8') as file:
            for line in file:
                try:
                    data = json.loads(line)
                    t = data.get('type')
                    if t in ('USER_INPUT', 'PLANNER_RESPONSE'):
                        content = data.get('content', '')
                        content_lower = content.lower()
                        if any(kw in content_lower for kw in keywords):
                            print(f'[{t}]: {content[:500]}...')
                            print('-' * 80)
                except Exception as e:
                    pass
    except Exception as e:
        print(f"Error reading file {f}: {e}")
