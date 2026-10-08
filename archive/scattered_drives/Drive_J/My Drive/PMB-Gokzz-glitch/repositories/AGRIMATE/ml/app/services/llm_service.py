import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
client = AsyncAnthropic(api_key=api_key) if api_key else None

async def generate_agri_response(text: str) -> str:
    if not client:
        print("[DEV] Mock LLM response")
        return "This is a mock response from Claude giving agricultural advice."
        
    prompt = f"""You are Agrimate, an AI-powered smart farming assistant.
A farmer has asked you the following question or made the following statement:
"{text}"

Provide a concise, helpful, and easily understandable response in the same language. 
Keep it under 3 sentences as it will be read aloud via voice."""
    
    response = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=150,
        temperature=0.3,
        system="You are an expert agronomist providing tailored advice to farmers.",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.content[0].text
