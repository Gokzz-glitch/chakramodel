import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.stt_service import transcribe_audio
from app.services.llm_service import generate_agri_response
from app.services.tts_service import generate_speech
from app.services.ocr_service import extract_soil_data
from app.services.soil_score_service import calculate_soil_health
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()

class SoilDataModel(BaseModel):
    soil_data: Dict[str, Any]
    language: str = "en"

@router.post("/soil-score")
async def get_soil_health_score(payload: SoilDataModel):
    try:
        health_report = await calculate_soil_health(payload.soil_data, payload.language)
        return {
            "success": True,
            "report": health_report
        }
    except Exception as e:
        print(f"Error calculating soil score: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate soil health score")

@router.post("/soil-report")
async def process_soil_report(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        raise HTTPException(status_code=400, detail="Invalid image format. Supported formats: PNG, JPG, JPEG, WEBP")
    
    temp_image_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_image:
            content = await file.read()
            temp_image.write(content)
            temp_image_path = temp_image.name
            
        # Extract data using Claude Vision
        extracted_data = await extract_soil_data(temp_image_path)
        
        return {
            "success": True,
            "data": extracted_data
        }
    except Exception as e:
        print(f"Error processing soil report: {e}")
        raise HTTPException(status_code=500, detail="Failed to process soil report image")
    finally:
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)

@router.post("/voice")
async def process_voice_input(file: UploadFile = File(...)):
    if not file.filename.endswith(('.wav', '.mp3', '.m4a', '.ogg', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid audio format")
    
    temp_audio_path = ""
    try:
        # Save uploaded file to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            content = await file.read()
            temp_audio.write(content)
            temp_audio_path = temp_audio.name
            
        # 1. Speech to Text: Transcribe the farmer's voice 
        text = await transcribe_audio(temp_audio_path)
        
        # 2. LLM processing: Get advice from Claude
        response_text = await generate_agri_response(text)
        
        # 3. Text to Speech: Convert Claude's text response back to voice
        audio_base64 = await generate_speech(response_text)
        
        return {
            "transcription": text,
            "response_text": response_text,
            "audio_base64": audio_base64
        }
    except Exception as e:
        print(f"Error processing voice: {e}")
        raise HTTPException(status_code=500, detail="Failed to process voice input")
    finally:
        # Clean up temporary audio file
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
