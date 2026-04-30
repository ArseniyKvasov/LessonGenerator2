import json
from typing import Any, Optional

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateReferencesRequest
from app.utils.text import trim_to_words_limit, trim_topic_to_chars


def build_reference_prompt(
    request_data: GenerateReferencesRequest,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "user_request": request_data.user_request,
        "lesson_topic": request_data.topic,
        "sections": [section.model_dump() for section in request_data.sections],
        "task": (
            "Generate compact structured references for all provided lesson sections "
            "in one response. Each section must get its own reference."
        ),
        "main_goal": (
            "Distribute lesson content across sections and create compact references. "
            "Each reference must include all useful items needed for exercise generation, "
            "but points must stay short, atomic, and non-explanatory."
        ),
        "rules": [
            "Return only valid JSON.",
            "Do not add explanations outside JSON.",
            "Return exactly one section output per input section.",
            "Keep section order exactly as in the input.",
            "Keep each section title exactly the same as in the input.",

            "Before writing references, mentally distribute the lesson content across all sections.",
            "Each section implicitly has a role based on its title.",
            "Interpret the role of each section from its title before generating content.",
            "Each section must receive only the content that best belongs to that section compared to the other provided sections.",
            "Do not front-load the lesson content into early sections.",
            "If a concept can fit multiple sections, place it in the most specific section, not the broadest one.",
            "Do not repeat the same concepts, examples, rules, or exercise focus across multiple sections unless needed for review.",

            "Opening sections should introduce context, purpose, or motivation.",
            "Opening sections must not cover detailed subtopics that have their own later sections.",
            "Opening sections should avoid full rules, full structures, long lists, and advanced variations.",
            "Review or final sections should consolidate previous content, not introduce new detailed theory.",

            "section_goal must be one concise sentence about what the student will learn or practice in that section only.",

            "points must be complete but concise within each section scope.",
            "Do not limit the number of points.",
            "Do not explain points.",
            "Each point must be short and atomic.",
            "Prefer short labels, examples, or item lists over long explanatory sentences.",
            "Use detailed coverage by quantity of useful items, not by length of explanation.",
            "Include all required vocabulary items if the section is vocabulary-focused.",
            "Include all required examples if the section needs examples.",
            "Include all required steps if the section is process-focused.",
            "Do not write teacher-facing methodology inside points.",
            "Every point must directly support exercise generation for that section.",

            "practice_focus must be one concise sentence describing what kind of exercises should be generated.",
            "Consider that it is an individual lesson.",
            "All content must match the lesson topic and each section purpose.",
        ],
        "response_schema": {
            "sections": [
                {
                    "title": "string",
                    "reference": {
                        "section_goal": "string",
                        "points": ["string"],
                        "practice_focus": "string",
                    },
                }
            ]
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = (
            "Regenerate the response and fix this validation error. "
            "Return only valid JSON that matches the schema."
        )

    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_reference_result(
    data: dict[str, Any],
    request_data: GenerateReferencesRequest,
) -> tuple[bool, Optional[str], Optional[list[dict[str, Any]]]]:
    if "sections" not in data:
        return False, "Missing field: sections", None

    items = data["sections"]
    source_sections = request_data.sections

    if not isinstance(items, list):
        return False, "sections must be a list", None

    if len(items) != len(source_sections):
        return False, "sections count must match input sections count", None

    cleaned_sections: list[dict[str, Any]] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            return False, "Invalid section format", None

        title = item.get("title")
        reference = item.get("reference")
        source_title = source_sections[index].title

        if not isinstance(title, str) or not title.strip():
            return False, "Invalid title", None

        if title.strip() != source_title:
            return False, "Section title mismatch", None

        if not isinstance(reference, dict):
            return False, "Invalid reference", None

        section_goal = reference.get("section_goal")
        points = reference.get("points")
        if points is None:
            # Backward compatibility for model outputs using old field name.
            points = reference.get("key_points")
        practice_focus = reference.get("practice_focus")

        if not isinstance(section_goal, str) or not section_goal.strip():
            return False, "Invalid section_goal", None

        if not isinstance(practice_focus, str) or not practice_focus.strip():
            return False, "Invalid practice_focus", None

        if not isinstance(points, list) or not points:
            return False, "points must be a non-empty list", None

        cleaned_points = [
            point.strip()
            for point in points
            if isinstance(point, str) and point.strip()
        ]

        if not cleaned_points:
            return False, "points invalid", None

        cleaned_sections.append({
            "title": trim_topic_to_chars(source_title, 40),
            "reference": {
                "section_goal": section_goal.strip(),
                "points": cleaned_points,
                "practice_focus": practice_focus.strip(),
            },
        })

    return True, None, cleaned_sections


async def generate_references(request_data: GenerateReferencesRequest) -> dict[str, Any]:
    settings = get_settings()
    user_request = trim_to_words_limit(request_data.user_request, max_words=1000)
    normalized_request = request_data.model_copy(update={"user_request": user_request})

    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_reference_prompt(
            request_data=normalized_request,
            previous_error=previous_error,
        )

        result = await generate(prompt=prompt, model_type="pro")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, sections = validate_reference_result(
            result["data"],
            normalized_request,
        )

        if is_valid and sections:
            return {
                "status": "ok",
                "sections": sections,
            }

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate section references",
    }
