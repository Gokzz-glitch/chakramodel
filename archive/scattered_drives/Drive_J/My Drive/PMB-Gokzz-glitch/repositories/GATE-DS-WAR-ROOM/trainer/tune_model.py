import time
from google import genai
from google.genai import types

def start_tuning():
    print("Initializing GenAI Client...")
    # Assumes GEMINI_API_KEY is in the environment
    client = genai.Client()
    
    file_path = "data/training_data.jsonl"
    print(f"Uploading {file_path} to Gemini servers...")
    
    # 1. Upload the dataset
    training_file = client.files.upload(
        file=file_path,
        config={'display_name': 'gate-da-training-data'}
    )
    
    print(f"Uploaded file: {training_file.name}")
    
    # 2. Start the Tuning Job
    print("Starting fine-tuning job on gemini-2.5-flash...")
    tuning_job = client.tunings.tune(
        base_model='models/gemini-2.5-flash',
        training_dataset=types.TuningDataset(
            examples=training_file.name,
        ),
        config=types.CreateTuningJobConfig(
            epoch_count=5,
            tuned_model_display_name="gate-da-expert-v1",
            description="Fine-tuned model for GATE DA preparation"
        )
    )
    
    print(f"Tuning Job Started! Job Name: {tuning_job.name}")
    print(f"Your Custom Model ID will be: {tuning_job.tuned_model.model}")
    print("\nNOTE: Tuning takes some time. You can check the status in Google AI Studio.")
    print("Once complete, copy the Custom Model ID and paste it into the War Room Settings!")

if __name__ == "__main__":
    start_tuning()
