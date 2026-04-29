import json
from typing import Any, Optional

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateReferencesRequest
from app.utils.text import trim_to_words_limit, trim_topic_to_chars


def build_references_prompt(
    request_data: GenerateReferencesRequest,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "user_request": request_data.user_request,
        "lesson_topic": request_data.topic,
        "sections": [s.model_dump() for s in request_data.sections],
        "task": (
            "For each section, generate a structured reference that will be used "
            "to create exercises."
        ),
        "rules": [
            "Return only valid JSON.",
            "For each section create reference with fields:",
            "lesson_topic, section_goal, key_points, practice_focus.",
            "lesson_topic must match provided lesson_topic.",
            "section_goal must clearly describe what the student will learn.",
            "key_points must be a list of 2-5 short items.",
            "practice_focus must describe what kind of exercises to generate.",
        ],
        "response_schema": {
            "sections": [
                {
                    "title": "string",
                    "reference": {
                        "lesson_topic": "string",
                        "section_goal": "string",
                        "key_points": ["string"],
                        "practice_focus": "string",
                    },
                }
            ]
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = "Regenerate the response and fix this error."

    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_references_result(
    data: dict[str, Any],
    request_data: GenerateReferencesRequest,
) -> tuple[bool, Optional[str], Optional[list[dict[str, Any]]]]:
    if "sections" not in data:
        return False, "Missing field: sections", None

    if not isinstance(data["sections"], list):
        return False, "sections must be a list", None

    if len(data["sections"]) != len(request_data.sections):
        return False, "sections count mismatch", None

    result = []

    for item in data["sections"]:
        if not isinstance(item, dict):
            return False, "Invalid section format", None

        title = item.get("title")
        ref = item.get("reference")

        if not isinstance(title, str) or not title.strip():
            return False, "Invalid title", None

        if not isinstance(ref, dict):
            return False, "Invalid reference", None

        lesson_topic = ref.get("lesson_topic")
        section_goal = ref.get("section_goal")
        key_points = ref.get("key_points")
        practice_focus = ref.get("practice_focus")

        if not all(isinstance(x, str) and x.strip() for x in [lesson_topic, section_goal, practice_focus]):
            return False, "Invalid reference fields", None

        if not isinstance(key_points, list) or not key_points:
            return False, "key_points must be non-empty list", None

        cleaned_points = [
            p.strip() for p in key_points if isinstance(p, str) and p.strip()
        ]

        if not cleaned_points:
            return False, "key_points invalid", None

        result.append({
            "title": trim_topic_to_chars(title, 40),
            "reference": {
                "lesson_topic": lesson_topic.strip(),
                "section_goal": section_goal.strip(),
                "key_points": cleaned_points[:5],
                "practice_focus": practice_focus.strip(),
            },
        })

    return True, None, result


async def generate_references(request_data: GenerateReferencesRequest) -> dict[str, Any]:
    settings = get_settings()

    request_data.user_request = trim_to_words_limit(
        request_data.user_request,
        max_words=1000,
    )

    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_references_prompt(
            request_data=request_data,
            previous_error=previous_error,
        )

        result = await generate(prompt=prompt, model_type="pro")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, sections = validate_references_result(
            result["data"],
            request_data,
        )

        if is_valid and sections:
            return {
                "status": "ok",
                "sections": sections,
            }

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate references",
    }
