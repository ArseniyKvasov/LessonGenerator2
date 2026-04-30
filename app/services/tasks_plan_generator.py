import json
from typing import Any, Optional

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateTasksPlanRequest


TASK_TYPES_AVAILABLE = [
    "note",
    "reading_text",
    "word_list",
    "test",
    "true_or_false",
    "fill_gaps",
    "image",
    "match_cards",
    "audio",
    "speaking_cards",
    "words_to_pronounce",
]


def build_tasks_plan_prompt(
    request_data: GenerateTasksPlanRequest,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "lesson_topic": request_data.lesson_topic,
        "sections": [section.model_dump() for section in request_data.sections],
        "task_types_available": TASK_TYPES_AVAILABLE,
        "task": (
            "Create a task plan for all lesson sections in one response. "
            "Do not generate the task content yet. "
            "Only choose task types and explain the purpose of each task."
        ),
        "rules": [
            "Return only valid JSON.",
            "Do not add explanations outside JSON.",
            "Use only task types from task_types_available.",

            "Return exactly one section output per input section.",
            "Keep section order exactly as in the input.",
            "Keep each section title exactly the same as in the input.",

            "Each section must have 2-4 tasks.",
            "Each task must have type and purpose.",
            "Do not repeat task types inside one section.",

            "Each task must be based on the section reference: section_goal, points, and practice_focus.",
            "Choose task types by matching them to the practice_focus of the section.",
            "Do not choose task types that are not directly supported by the section reference.",
            "Do not add media tasks such as image or audio unless the section reference explicitly requires visual or listening input.",

            "Purpose must clearly explain what this task trains or checks.",
            "Consider it is an individual lesson.",

            "Prefer an educational flow from explanation to practice when the section introduces new material.",
            "Use note only when the section introduces new concepts, rules, examples, or instructions.",
            "Do not add note only to satisfy the explain-practice flow.",
            "Practice-focused sections may contain only practice tasks.",

            "For introductory sections, prefer light recognition, context-setting, visual, or discussion tasks.",
            "For review or final sections, prefer mixed practice, tests, error correction, or reflection tasks over new explanation.",

            "Avoid overusing the same task type across many sections unless it is strongly justified by the reference.",
            "Keep the lesson varied, but do not sacrifice relevance for variety.",
        ],
        "response_schema": {
            "sections": [
                {
                    "title": "string",
                    "tasks": [
                        {
                            "type": "note",
                            "purpose": "string",
                        }
                    ],
                }
            ]
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = "Regenerate the response and fix this error."

    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_tasks_plan_result(
    data: dict[str, Any],
    request_data: GenerateTasksPlanRequest,
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
            return False, "Each section must be an object", None

        source_section = source_sections[index]
        title = item.get("title")
        tasks = item.get("tasks")

        if not isinstance(title, str) or not title.strip():
            return False, "Section title cannot be empty", None

        # Keep section mapping by index to avoid hard failures on harmless title rewrites.
        # Final title is always taken from source_section below.

        if not isinstance(tasks, list):
            return False, "tasks must be a list", None

        if len(tasks) < 2 or len(tasks) > 4:
            return False, "Section must have 2-4 tasks", None

        note_count = 0
        reading_count = 0
        image_count = 0
        audio_count = 0

        cleaned_tasks = []

        for task in tasks:
            if not isinstance(task, dict):
                return False, "Each task must be an object", None

            task_type = task.get("type")
            purpose = task.get("purpose")

            if task_type not in TASK_TYPES_AVAILABLE:
                return False, f"Invalid task type: {task_type}", None

            if not isinstance(purpose, str) or not purpose.strip():
                return False, "Task purpose cannot be empty", None

            if task_type == "note":
                note_count += 1

            if task_type == "reading_text":
                reading_count += 1

            if task_type == "image":
                image_count += 1

            if task_type == "audio":
                audio_count += 1

            cleaned_tasks.append({
                "type": task_type,
                "purpose": purpose.strip(),
            })

        if note_count > 1:
            return False, "Only one note is allowed per section", None

        if reading_count > 1:
            return False, "Only one reading_text is allowed per section", None

        if image_count > 1:
            return False, "Only one image is allowed per section", None

        if audio_count > 1:
            return False, "Only one audio is allowed per section", None

        cleaned_sections.append({
            "title": source_section.title,
            "reference": source_section.reference.model_dump(),
            "tasks": cleaned_tasks,
        })

    return True, None, cleaned_sections


async def generate_tasks_plan(request_data: GenerateTasksPlanRequest) -> dict[str, Any]:
    settings = get_settings()
    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_tasks_plan_prompt(
            request_data=request_data,
            previous_error=previous_error,
        )

        result = await generate(prompt=prompt, model_type="pro")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, sections = validate_tasks_plan_result(
            data=result["data"],
            request_data=request_data,
        )

        if is_valid and sections:
            return {
                "status": "ok",
                "sections": sections,
            }

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate valid tasks plan",
    }
