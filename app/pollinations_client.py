import base64
from typing import Any, Optional

import httpx

from app.config import get_settings


POLLINATIONS_BASE_URL = "https://gen.pollinations.ai"
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


def check_file_size(file_bytes: bytes, file_type: str) -> Optional[dict[str, Any]]:
    """
    Checks generated file size.

    Pollinations returns binary audio and can return base64 images.
    The limit must be checked against raw bytes, not base64 string length.
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return {
            "status": "error",
            "message": f"Generated {file_type} exceeds 15MB limit",
        }

    return None


async def generate_pollinations_image(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "medium",
    response_format: str = "b64_json",
) -> dict[str, Any]:
    """
    Generates an image through Pollinations OpenAI-compatible image endpoint.
    Returns image as URL or base64 depending on response_format.
    """
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{POLLINATIONS_BASE_URL}/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {settings.POLLINATIONS_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "flux",
                    "prompt": prompt,
                    "n": 1,
                    "size": size,
                    "quality": quality,
                    "response_format": response_format,
                },
            )

        if response.status_code >= 400:
            return {
                "status": "error",
                "message": response.text,
            }

        data = response.json()
        image_data = data.get("data", [{}])[0]

        if response_format == "url":
            image_url = image_data.get("url")

            if not image_url:
                return {
                    "status": "error",
                    "message": "Pollinations returned empty image URL",
                }

            return {
                "status": "ok",
                "response_format": response_format,
                "image": image_url,
            }

        image_base64 = image_data.get("b64_json")

        if not image_base64:
            return {
                "status": "error",
                "message": "Pollinations returned empty image base64",
            }

        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            return {
                "status": "error",
                "message": "Pollinations returned invalid image base64",
            }

        size_error = check_file_size(image_bytes, "image")

        if size_error:
            return size_error

        return {
            "status": "ok",
            "response_format": response_format,
            "image": image_base64,
        }

    except httpx.TimeoutException:
        return {
            "status": "error",
            "message": "Pollinations image generation timeout",
        }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }


async def generate_pollinations_audio(
    text: str,
    voice: str = "nova",
    response_format: str = "mp3",
    speed: float = 1.0,
) -> dict[str, Any]:
    """
    Generates speech through Pollinations OpenAI-compatible audio endpoint.
    Returns audio as base64.
    """
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{POLLINATIONS_BASE_URL}/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {settings.POLLINATIONS_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "elevenlabs",
                    "input": text,
                    "voice": voice,
                    "response_format": response_format,
                    "speed": speed,
                },
            )

        if response.status_code >= 400:
            return {
                "status": "error",
                "message": response.text,
            }

        audio_bytes = response.content

        if not audio_bytes:
            return {
                "status": "error",
                "message": "Pollinations returned empty audio",
            }

        size_error = check_file_size(audio_bytes, "audio")

        if size_error:
            return size_error

        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "status": "ok",
            "response_format": response_format,
            "audio_base64": audio_base64,
        }

    except httpx.TimeoutException:
        return {
            "status": "error",
            "message": "Pollinations audio generation timeout",
        }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }
