import json
from typing import Any, Optional

from pydantic import ValidationError

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateStyleRequest, GenerateStyleSuccessResponse


def build_style_prompt(
    request_data: GenerateStyleRequest,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": request_data.topic,
        "colors_available": request_data.colors_available,
        "icons_available": request_data.icons_available,
        "task": "Choose a visual style for this ESL lesson topic.",
        "rules": [
            "Return only valid JSON.",
            "color must be exactly one value from colors_available.",
            "icon must be exactly one value from icons_available.",
            "Do not invent values.",
        ],
        "response_schema": {
            "status": "ok",
            "color": "string from colors_available",
            "icon": "string from icons_available",
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = "Regenerate the response and fix this validation error."

    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_style_response(
    data: dict[str, Any],
    request_data: GenerateStyleRequest,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    try:
        parsed = GenerateStyleSuccessResponse.model_validate(data)
    except ValidationError as error:
        return False, str(error), None

    if parsed.color not in request_data.colors_available:
        return False, "color must strictly match colors_available", None
    if parsed.icon not in request_data.icons_available:
        return False, "icon must strictly match icons_available", None

    return True, None, parsed.model_dump()


async def generate_style(request_data: GenerateStyleRequest) -> dict[str, Any]:
    settings = get_settings()
    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        result = await generate(
            prompt=build_style_prompt(request_data, previous_error=previous_error),
            temperature=0,
        )

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, style = validate_style_response(result["data"], request_data)
        if is_valid and style:
            return style

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate valid style",
    }
