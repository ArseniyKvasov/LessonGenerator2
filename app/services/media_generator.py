from typing import Any

from app.pollinations_client import (
    generate_pollinations_audio,
    generate_pollinations_image,
)
from app.schemas import GenerateAudioRequest, GenerateImageRequest


def build_audio_text(request_data: GenerateAudioRequest) -> str:
    """
    Converts structured audio script into plain text for text-to-speech.
    Dialogue keeps speaker names, monologue returns narrator text only.
    """
    if request_data.audio_type == "monologue":
        return " ".join(item.text.strip() for item in request_data.script)

    replicas = []

    for item in request_data.script:
        replicas.append(f"{item.speaker.strip()}: {item.text.strip()}")

    return "\n".join(replicas)


async def generate_image_file(request_data: GenerateImageRequest) -> dict[str, Any]:
    return await generate_pollinations_image(
        prompt=request_data.detailed_description,
        size=request_data.size,
        quality=request_data.quality,
        response_format=request_data.response_format,
    )


async def generate_audio_file(request_data: GenerateAudioRequest) -> dict[str, Any]:
    audio_text = build_audio_text(request_data)

    if len(audio_text) > 4096:
        return {
            "status": "error",
            "message": "Audio script is too long. Maximum is 4096 characters.",
        }

    return await generate_pollinations_audio(
        text=audio_text,
        voice=request_data.voice,
        response_format=request_data.response_format,
        speed=request_data.speed,
    )
