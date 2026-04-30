import json
from typing import Any, Optional

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateSectionsRequest, ImproveSectionRequest
from app.utils.text import trim_to_words_limit, trim_topic_to_chars


def build_new_sections_prompt(
    user_request: str,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "user_request": user_request,
        "task": (
            "Form a list of interactive lesson sections. "
            "Each section title must be 1-2 words. "
            "Consider that each section will consist of both theory and practice."
        ),
        "rules": [
            "Return only valid JSON.",
            "Generate several sections.",
            "Each section title must be 1-2 words.",
        ],
        "response_schema": {
            "sections": [
                {
                    "title": "string"
                }
            ]
        },
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_improve_sections_prompt(
    user_request: str,
    sections: list[dict[str, str]],
    improvement_request: str,
) -> str:
    payload = {
        "user_request": user_request,
        "sections": sections,
        "improvement_request": improvement_request,
        "task": (
            "Improve section titles according to the user's request. "
            "Return improved interactive lesson sections."
        ),
        "rules": [
            "Return only valid JSON.",
            "Each section title must be 1-2 words.",
            "Each section title must be <= 40 characters.",
            "Sections must be suitable for an interactive lesson.",
            "Keep section order.",
            "Do not add explanations.",
        ],
        "response_schema": {
            "sections": [
                {
                    "title": "string"
                }
            ]
        },
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_sections_result(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[list[dict[str, str]]]]:
    if "sections" not in data:
        return False, "Missing field: sections", None

    if not isinstance(data["sections"], list):
        return False, "sections must be a list", None

    if not data["sections"]:
        return False, "sections cannot be empty", None

    sections = []

    for item in data["sections"]:
        if not isinstance(item, dict):
            return False, "Each section must be an object", None

        title = item.get("title")

        if not isinstance(title, str) or not title.strip():
            return False, "Each section must have non-empty title", None

        title = trim_topic_to_chars(title, max_chars=40)
        words = [part for part in title.split() if part]

        sections.append({
            "title": title,
        })

    return True, None, sections


async def generate_new_sections(request_data: GenerateSectionsRequest) -> dict[str, Any]:
    settings = get_settings()
    user_request = trim_to_words_limit(request_data.user_request, max_words=1000)

    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_new_sections_prompt(
            user_request=user_request,
            previous_error=previous_error,
        )

        result = await generate(prompt=prompt, model_type="pro")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, sections = validate_sections_result(result["data"])

        if is_valid and sections:
            return {
                "status": "ok",
                "sections": sections,
            }

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate valid sections",
    }


async def improve_sections(request_data: ImproveSectionRequest) -> dict[str, Any]:
    settings = get_settings()

    user_request = trim_to_words_limit(request_data.user_request, max_words=1000)
    improvement_request = trim_to_words_limit(
        request_data.improvement_request,
        max_words=300,
    )
    source_sections = [section.model_dump() for section in request_data.sections]

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_improve_sections_prompt(
            user_request=user_request,
            sections=source_sections,
            improvement_request=improvement_request,
        )

        result = await generate(prompt=prompt, model_type="light")

        if result["status"] == "error":
            continue

        is_valid, error_message, sections = validate_sections_result(result["data"])

        if is_valid and sections:
            return {
                "status": "ok",
                "sections": sections,
            }

    return {
        "status": "error",
        "message": "Could not improve sections",
    }
