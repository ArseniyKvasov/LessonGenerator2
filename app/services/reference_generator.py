import json
from typing import Any, Optional

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateReferencesRequest, GenerateSectionReferenceRequest
from app.utils.text import trim_to_words_limit, trim_topic_to_chars


def build_reference_prompt(
    request_data: GenerateSectionReferenceRequest,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "user_request": request_data.user_request,
        "lesson_topic": request_data.topic,
        "section": request_data.section.model_dump(),
        "task": (
            "Generate a detailed structured reference for this lesson section "
            "that will later be used to create exercises."
        ),
        "main_goal": (
            "The reference must contain all important content needed for exercise "
            "generation inside this section."
        ),
        "rules": [
            "Return only valid JSON.",
            "Do not add explanations outside JSON.",
            "Generate exactly one reference for the provided section.",
            "Keep the same section title as in the input.",
            "section_goal must clearly describe what the student will learn or practice.",
            "key_points must contain all important material needed to generate exercises.",
            "Do not limit key_points to 3-5 items - write detailed materials.",
            "practice_focus must describe what kind of exercises should be generated from this reference.",
            "All content must match the lesson topic and the section purpose.",
        ],
        "response_schema": {
            "section": {
                "title": "string",
                "reference": {
                    "section_goal": "string",
                    "key_points": ["string"],
                    "practice_focus": "string",
                },
            }
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = (
            "Regenerate the response and fix this error. "
            "Return only valid JSON that matches the schema."
        )

    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_reference_result(
    data: dict[str, Any],
    request_data: GenerateSectionReferenceRequest,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    if "section" not in data:
        return False, "Missing field: section", None

    item = data["section"]

    if not isinstance(item, dict):
        return False, "Invalid section format", None

    title = item.get("title")
    reference = item.get("reference")

    if not isinstance(title, str) or not title.strip():
        return False, "Invalid title", None

    if title.strip() != request_data.section.title:
        return False, "Section title mismatch", None

    if not isinstance(reference, dict):
        return False, "Invalid reference", None

    section_goal = reference.get("section_goal")
    key_points = reference.get("key_points")
    practice_focus = reference.get("practice_focus")

    if not isinstance(section_goal, str) or not section_goal.strip():
        return False, "Invalid section_goal", None

    if not isinstance(practice_focus, str) or not practice_focus.strip():
        return False, "Invalid practice_focus", None

    if not isinstance(key_points, list) or not key_points:
        return False, "key_points must be a non-empty list", None

    cleaned_key_points = [
        point.strip()
        for point in key_points
        if isinstance(point, str) and point.strip()
    ]

    if not cleaned_key_points:
        return False, "key_points invalid", None

    return True, None, {
        "title": trim_topic_to_chars(request_data.section.title, 40),
        "reference": {
            "lesson_topic": request_data.topic,
            "section_goal": section_goal.strip(),
            "key_points": cleaned_key_points,
            "practice_focus": practice_focus.strip(),
        },
    }


async def generate_section_reference(
    request_data: GenerateSectionReferenceRequest,
) -> dict[str, Any]:
    settings = get_settings()
    user_request = trim_to_words_limit(request_data.user_request, max_words=1000)
    section_request = request_data.model_copy(update={"user_request": user_request})

    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_reference_prompt(
            request_data=section_request,
            previous_error=previous_error,
        )

        result = await generate(prompt=prompt, model_type="pro")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, section = validate_reference_result(
            result["data"],
            section_request,
        )

        if is_valid and section:
            return {
                "status": "ok",
                "section": section,
            }

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate section reference",
    }


async def generate_references(request_data: GenerateReferencesRequest) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []

    for section in request_data.sections:
        section_request = GenerateSectionReferenceRequest(
            user_request=request_data.user_request,
            topic=request_data.topic,
            section=section,
        )
        result = await generate_section_reference(section_request)

        if result["status"] == "error":
            return result

        sections.append(result["section"])

    return {
        "status": "ok",
        "sections": sections,
    }
