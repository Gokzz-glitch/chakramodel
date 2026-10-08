import asyncio
import json
import os
import pydantic
from pathlib import Path
from datetime import datetime
from google.antigravity import Agent, LocalAgentConfig, types

# Ensure the output directory exists
output_file = Path("m:/chakramodel/september1to4afternnon_chat.json")
output_file.parent.mkdir(parents=True, exist_ok=True)

env_file = Path("m:/chakramodel/.env")
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY='):
                os.environ['GEMINI_API_KEY'] = line.strip().split('=', 1)[1].strip("'\"")

class ExtractionResult(pydantic.BaseModel):
    file_name: str
    file_path: str
    timestamp_processed: str
    file_type: str
    extracted_content: dict
    key_metrics_and_values: list[str]

files_to_process = [
    r"C:\Users\imgk3\Downloads\yolov1 paper.pdf",
    r"C:\Users\imgk3\Downloads\altered-om.ipynb",
    r"C:\Users\imgk3\Downloads\Kaggle_ChakraTransformer_Conformal_FIXED.ipynb",
    r"C:\Users\imgk3\Downloads\combo-6-om (3).ipynb",
    r"C:\Users\imgk3\Downloads\combo-6-om (2).ipynb",
    r"C:\Users\imgk3\Downloads\combo-6-om (1).ipynb",
    r"C:\Users\imgk3\Downloads\combo-6-om.ipynb",
    r"C:\Users\imgk3\Downloads\chakratransformer_COMBO 6 ISSUES.pdf",
    r"C:\Users\imgk3\Downloads\KAGGLE_SETUP_GUIDE.md",
    r"C:\Users\imgk3\Downloads\KRISHNA_OM_$.ipynb",
    r"C:\Users\imgk3\Downloads\notebooka59636e6bb.ipynb",
    r"C:\Users\imgk3\Downloads\notebookb6c3100a14 (2).ipynb",
    r"C:\Users\imgk3\Downloads\Kaggle_ChakraTransformer_Evaluation_Standalone_FIXED.ipynb",
    r"C:\Users\imgk3\Downloads\notebookb6c3100a14 (1).ipynb",
    r"C:\Users\imgk3\Downloads\notebookb6c3100a14.ipynb",
    r"C:\Users\imgk3\Downloads\chakramodel-evaluation-4.ipynb",
    r"C:\Users\imgk3\Downloads\notebookebd2f4d761.ipynb",
    r"C:\Users\imgk3\Downloads\chakranet_merged.pdf",
    r"C:\Users\imgk3\Downloads\chakramodel-testing (6).ipynb",
    r"C:\Users\imgk3\Downloads\chakramodel-testing (5).ipynb",
    r"C:\Users\imgk3\Downloads\chakramodel-testing (3).ipynb",
    r"C:\Users\imgk3\Downloads\chakramodel-testing (4).ipynb",
    r"C:\Users\imgk3\Downloads\chakramodel-testing (2).ipynb",
    r"C:\Users\imgk3\Downloads\chakramodel-testing (1).ipynb",
    r"C:\Users\imgk3\Downloads\chakramodel-testing.ipynb",
    r"C:\Users\imgk3\Downloads\implementation_plan rajapalayam.md",
    r"C:\Users\imgk3\Downloads\Download Colonoscopy Research Papers.pdf",
    r"C:\Users\imgk3\Downloads\colonoscopy_60_papers.jsx",
    r"C:\Users\imgk3\Downloads\implementation_plan.md",
    r"C:\Users\imgk3\Downloads\chakra_analysis_and_prompt.md",
    r"C:\Users\imgk3\Downloads\ChakraModel_presentataion.pptx",
    r"C:\Users\imgk3\Downloads\ChakraModel_Full_Pitch.pptx",
    r"C:\Users\imgk3\Downloads\proof.jpeg",
    r"C:\Users\imgk3\Downloads\generate_pitch.py",
    r"C:\Users\imgk3\Downloads\slides_structure.txt",
    r"C:\Users\imgk3\Downloads\ChakraModel_SaaS_Pitch.pptx",
    r"C:\Users\imgk3\Downloads\ChakraModel_16Slide_Pitch.pptx",
    r"C:\Users\imgk3\Downloads\ChakraModel_Final_Pitch.pptx",
    r"C:\Users\imgk3\Downloads\hackathon_pitch_deck_template.pdf",
    r"C:\Users\imgk3\Downloads\hackathon_pitch_deck_template.pptx",
    r"C:\Users\imgk3\Downloads\1st success.mp4",
    r"C:\Users\imgk3\Downloads\ChakraModel_Pitch_Deck (1).pptx",
    r"C:\Users\imgk3\Downloads\calude analysis.html",
]

async def process_file(file_path_str: str, sem: asyncio.Semaphore):
    async with sem:
        try:
            p = Path(file_path_str)
            if not p.exists():
                print(f"File not found: {p}")
                return None
            
            ext = p.suffix.lower()
            contents = [f"Extract all data exhaustively from this file: {p.name}"]
            
            # Use appropriate type wrapper or plain text
            if ext == '.pdf':
                contents.append(types.Document.from_file(file_path_str))
            elif ext in ['.jpg', '.jpeg', '.png']:
                contents.append(types.Image.from_file(file_path_str))
            elif ext == '.mp4':
                contents.append(types.Video.from_file(file_path_str))
            elif ext in ['.pptx']:
                # PPTX might not be natively supported as Document, pass path and give tool.
                contents.append(f"Please read the file using your view_file tool at path: {file_path_str}")
            else:
                # Code files / text files
                with open(file_path_str, 'r', encoding='utf-8', errors='ignore') as f:
                    file_text = f.read()
                contents.append(f"\n```\n{file_text}\n```\n")

            config = LocalAgentConfig(
                capabilities=types.CapabilitiesConfig(
                    enabled_tools=[types.BuiltinTools.VIEW_FILE]
                ),
                response_schema=ExtractionResult,
            )
            
            async with Agent(config) as agent:
                response = await agent.chat(contents)
                data = await response.structured_output()
                if not data:
                    print(f"Failed to extract structured output for {p.name}")
                    return None
                
                # Update known fields just in case
                data['file_name'] = p.name
                data['file_path'] = str(p)
                data['timestamp_processed'] = datetime.utcnow().isoformat()
                data['file_type'] = ext.strip('.')
                
                print(f"Successfully processed {p.name}")
                return data
                
        except Exception as e:
            print(f"Error processing {file_path_str}: {e}")
            return None

async def main():
    sem = asyncio.Semaphore(3) # Limit concurrency
    
    # Check existing data to resume
    existing_data = []
    processed_paths = set()
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    existing_data = json.loads(content)
                    processed_paths = {item['file_path'] for item in existing_data}
        except Exception as e:
            print(f"Could not read existing json: {e}")

    tasks = []
    for fp in files_to_process:
        if fp not in processed_paths:
            tasks.append(process_file(fp, sem))
        else:
            print(f"Skipping already processed file: {Path(fp).name}")
            
    if not tasks:
        print("All files processed!")
        return

    print(f"Processing {len(tasks)} files...")
    results = await asyncio.gather(*tasks)
    
    for res in results:
        if res:
            existing_data.append(res)
            
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=2)
        
    print(f"Saved {len(existing_data)} records to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
