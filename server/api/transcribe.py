"""Transcription API - proxies to OpenAI Whisper."""
import io
import math
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from pydantic import BaseModel
import openai

from server.config import get_settings
from server.auth.jwt import get_current_user
from server.db import record_usage, get_user_by_id
from server.db.models import User


router = APIRouter(prefix="/api/transcribe", tags=["transcribe"])


class TranscribeResponse(BaseModel):
    """Transcription response."""
    text: str
    duration_seconds: float
    credits_used: int
    credits_remaining: int


class TranscribeError(BaseModel):
    """Transcription error response."""
    error: str
    code: str


def calculate_credits(duration_seconds: float) -> int:
    """Calculate credits for audio duration.
    
    Billing: 1 credit per 15 seconds of audio (minimum 1 credit).
    """
    return max(1, math.ceil(duration_seconds / 15))


@router.post(
    "",
    response_model=TranscribeResponse,
    responses={
        402: {"model": TranscribeError, "description": "Insufficient credits"},
        500: {"model": TranscribeError, "description": "Transcription failed"},
    }
)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Transcribe audio using OpenAI Whisper API.
    
    Accepts audio files (mp3, wav, m4a, webm, mp4, mpeg, mpga, oga, ogg, flac).
    Credits are deducted based on audio duration (1 credit per 15 seconds).
    """
    settings = get_settings()
    
    # Read audio data
    audio_data = await audio.read()
    
    # Estimate duration from file size (rough estimate: ~16kB/sec for typical audio)
    # Whisper will return actual duration after processing
    estimated_duration = len(audio_data) / 16000
    estimated_credits = calculate_credits(estimated_duration)
    
    # Check if user has enough credits
    if current_user.credits < estimated_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Insufficient credits",
                "code": "INSUFFICIENT_CREDITS",
                "credits_needed": estimated_credits,
                "credits_available": current_user.credits,
            }
        )
    
    # Call OpenAI Whisper API
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        # Create file-like object
        audio_file = io.BytesIO(audio_data)
        audio_file.name = audio.filename or "audio.wav"
        
        # Transcribe
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="verbose_json"  # Get duration info
        )
        
        # Get actual duration
        actual_duration = getattr(transcription, 'duration', estimated_duration)
        credits_used = calculate_credits(actual_duration)
        
        # Record usage and deduct credits
        await record_usage(
            user_id=current_user.id,
            action="transcribe",
            credits_used=credits_used,
            duration_seconds=actual_duration,
            metadata={
                "filename": audio.filename,
                "file_size": len(audio_data),
                "language": language,
            }
        )
        
        # Get updated balance
        updated_user = await get_user_by_id(current_user.id)
        
        return TranscribeResponse(
            text=transcription.text,
            duration_seconds=actual_duration,
            credits_used=credits_used,
            credits_remaining=updated_user.credits
        )
        
    except openai.APIError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": f"Transcription failed: {str(e)}",
                "code": "TRANSCRIPTION_FAILED",
            }
        )


@router.get("/estimate")
async def estimate_credits(
    duration_seconds: float,
    current_user: User = Depends(get_current_user)
) -> dict:
    """Estimate credits needed for audio of given duration."""
    credits_needed = calculate_credits(duration_seconds)
    
    return {
        "duration_seconds": duration_seconds,
        "credits_needed": credits_needed,
        "credits_available": current_user.credits,
        "can_afford": current_user.credits >= credits_needed,
    }
