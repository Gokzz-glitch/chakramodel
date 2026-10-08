import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key) if api_key else None

async def transcribe_audio(file_path: str) -> str:
    if not client:
        print("[DEV] Mock STT transcription")
        return "This is a mock transcription of the farmer's voice input."
        
    with open(file_path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
    return transcript.text
