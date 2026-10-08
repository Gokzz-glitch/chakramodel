import os
import base64
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key) if api_key else None

async def generate_speech(text: str) -> str:
    if not client:
        print("[DEV] Mock TTS generation")
        # Return a dummy base64 string for testing without an API key
        return "UklGRkIAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YREAAAAA/wD/AP8A/wD/AP8A/wD/"
        
    response = await client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    )
    # Get the binary audio content
    audio_data = response.content
    
    # Return as base64 so frontend can play it directly
    return base64.b64encode(audio_data).decode('utf-8')
