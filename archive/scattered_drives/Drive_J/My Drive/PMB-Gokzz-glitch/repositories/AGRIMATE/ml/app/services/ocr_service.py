import os
import base64
from anthropic import AsyncAnthropic
import json

api_key = os.getenv("ANTHROPIC_API_KEY")
client = AsyncAnthropic(api_key=api_key) if api_key else None

async def extract_soil_data(image_path: str) -> dict:
    if not client:
        print("[DEV] Mock soil report extraction")
        return {
            "ph": 6.5,
            "nitrogen_n": "High",
            "phosphorus_p": "Medium",
            "potassium_k": "Low",
            "organic_carbon": "0.75%"
        }
        
    # Read the image and encode to base64
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")
        
    # Determine the media type
    media_type = "image/jpeg"
    if image_path.lower().endswith('.png'):
        media_type = "image/png"
    elif image_path.lower().endswith('.webp'):
        media_type = "image/webp"

    prompt = """Analyze this soil test report image and extract the key nutrient values.
Output ONLY a valid JSON object with the following keys, containing the extracted text values:
- "ph" (float or string)
- "nitrogen_n" (string, e.g. "Low", "Medium", "High", or a number)
- "phosphorus_p" (string)
- "potassium_k" (string)
- "organic_carbon" (string)
Do not include any other text, markdown formatting, or explanations."""

    response = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=300,
        temperature=0.1,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    )
    
    result_text = response.content[0].text.strip()
    
    try:
        # Sometimes Claude returns ```json ... ``` despite instructions
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        return json.loads(result_text)
    except Exception as e:
        print(f"Error parsing JSON from Claude: {e}\nRaw Text: {result_text}")
        raise ValueError("Failed to parse soil report data")
