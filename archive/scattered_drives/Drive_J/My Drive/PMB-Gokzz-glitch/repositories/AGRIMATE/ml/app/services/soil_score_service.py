import os
from anthropic import AsyncAnthropic
import json

api_key = os.getenv("ANTHROPIC_API_KEY")
client = AsyncAnthropic(api_key=api_key) if api_key else None

async def calculate_soil_health(soil_data: dict, language: str = 'en') -> dict:
    if not client:
        print("[DEV] Mock Soil Health Calculation")
        return {
            "score": 72,
            "status": "Fair",
            "deficiencies": ["Low Nitrogen", "Slightly Acidic pH"],
            "recommendations": [
                "Apply Urea or compost to increase Nitrogen levels.",
                "Consider adding agricultural lime to slightly raise the pH."
            ]
        }
        
    prompt = f"""You are an expert agronomist AI for the Agrimate platform.
Analyze the following soil test data and provide a comprehensive health score and recommendations.
The response must be in {language}.

Soil Data:
{json.dumps(soil_data, indent=2)}

Output ONLY a valid JSON object with the exact following structure:
{{
  "score": <integer from 0 to 100 representing overall health>,
  "status": "<string, e.g., 'Poor', 'Fair', 'Good', 'Excellent'>",
  "deficiencies": ["<list of strings detailing specific nutrient shortages or pH issues>"],
  "recommendations": ["<list of actionable, step-by-step corrective actions for the farmer>"]
}}
"""

    response = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        temperature=0.2,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    result_text = response.content[0].text.strip()
    
    try:
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        return json.loads(result_text)
    except Exception as e:
        print(f"Error parsing JSON from Claude: {e}\nRaw Text: {result_text}")
        raise ValueError("Failed to calculate soil health score")
