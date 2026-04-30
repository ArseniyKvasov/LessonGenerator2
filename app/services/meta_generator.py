import json
from typing import Any, Optional

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateMetaRequest
from app.utils.text import trim_to_words_limit, trim_topic_to_chars


def build_meta_prompt(
    request_data: GenerateMetaRequest,
    user_request: str,
    previous_error: Optional[str] = None,
) -> str:
    """
    Builds a strict prompt for generating lesson/task metadata.
    The model must choose color and icon from provided lists.
    Subject is either fixed (`subject`) or chosen from `subjects_available`.
    """
    payload = {
        "user_request": user_request,
        "colors_available": request_data.colors_available,
        "icons_available": request_data.icons_available,
        "rules": [
            "Return only valid JSON.",
            "topic must be a short title based on user_request.",
            "topic must be <= 40 characters.",
            "color must be exactly one value from colors_available.",
            "icon must be exactly one value from icons_available.",
            "Do not invent values.",
        ],
        "response_schema": {
            "topic": "string",
            "subject": "string",
            "color": "string",
            "icon": "string",
        },
    }
    if request_data.subject is not None:
        payload["subject"] = request_data.subject
        payload["rules"].append("subject must be exactly the provided subject value.")
    else:
        payload["subjects_available"] = request_data.subjects_available
        payload["rules"].append(
            "subject must be exactly one value from subjects_available."
        )

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = "Regenerate the response and fix this error."

    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_meta_result(
    data: dict[str, Any],
    request_data: GenerateMetaRequest,
) -> tuple[bool, Optional[str], Optional[dict[str, str]]]:
    required_fields = ["topic", "subject", "color", "icon"]

    for field in required_fields:
        if field not in data:
            return False, f"Missing field: {field}", None

        if not isinstance(data[field], str):
            return False, f"Field must be string: {field}", None

        if not data[field].strip():
            return False, f"Field cannot be empty: {field}", None

    topic = trim_topic_to_chars(data["topic"], max_chars=40)
    subject = data["subject"].strip()
    color = data["color"].strip()
    icon = data["icon"].strip()

    if request_data.subject is not None:
        if subject != request_data.subject:
            return False, "Subject must match provided subject", None
    elif (
        request_data.subjects_available is None
        or subject not in request_data.subjects_available
    ):
        return False, "Subject is not in subjects_available", None

    if color not in request_data.colors_available:
        return False, "Color is not in colors_available", None

    if icon not in request_data.icons_available:
        return False, "Icon is not in icons_available", None

    return True, None, {
        "topic": topic,
        "subject": subject,
        "color": color,
        "icon": icon,
    }


async def generate_meta(request_data: GenerateMetaRequest) -> dict[str, Any]:
    """
    Generates and validates metadata.
    If the generated result is invalid, tries to regenerate it.
    """
    settings = get_settings()
    user_request = trim_to_words_limit(request_data.user_request, max_words=1000)

    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_meta_prompt(
            request_data=request_data,
            user_request=user_request,
            previous_error=previous_error,
        )

        result = await generate(prompt=prompt, model_type="light")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, meta = validate_meta_result(
            data=result["data"],
            request_data=request_data,
        )

        if is_valid and meta:
            return {
                "status": "ok",
                **meta,
            }

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate valid meta",
    }
