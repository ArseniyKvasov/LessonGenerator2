import json
import re
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

from app.config import get_settings
from app.groq_client import generate
from app.schemas import GenerateTasksRequest, GeneratedTask


GeneratedTaskAdapter = TypeAdapter(GeneratedTask)


def build_tasks_prompt(
    request_data: GenerateTasksRequest,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "sections": [section.model_dump() for section in request_data.sections],
        "task": (
            "Generate full lesson tasks for each section. "
            "Use the provided task plan. "
            "Return tasks exactly in the requested JSON format."
        ),
        "rules": [
            "Return only valid JSON.",
            "Do not add markdown outside JSON.",
            "Generate task content only for task types from the provided task plan.",
            "Keep the same section order.",
            "Keep the same task order inside each section.",
            "Use section reference to generate relevant content.",
            "note.content supports Markdown + LaTeX.",
            "reading_text.content supports Markdown.",
            "test.questions must have 4-7 questions.",
            "test question supports Markdown + LaTeX.",
            "Each test question must have 2-4 options.",
            "Each test question must have exactly one correct option.",
            "true_or_false.statements must have 3-8 statements.",
            "true_or_false.statement supports Markdown + LaTeX.",
            "fill_gaps.text supports Markdown + LaTeX.",
            "fill_gaps.text must use ___ for every gap.",
            "fill_gaps.text must contain 4-10 gaps marked as ___.",
            "fill_gaps.answers must contain answers in the same order as gaps.",
            "fill_gaps.mode must be open or closed.",
            "image must return detailed_description only.",
            "audio must return audio_type and script.",
            "audio.audio_type must be monologue or dialogue.",
            "audio.script must be an array of replicas with speaker and text.",
            "For monologue, use one replica with speaker Narrator.",
            "For dialogue, use at least 4 replicas and at least 2 speakers.",
        ],
        "task_json_formats": {
            "note": {
                "type": "note",
                "content": "Markdown + LaTeX content",
            },
            "reading_text": {
                "type": "reading_text",
                "content": "Markdown content",
            },
            "word_list": {
                "type": "word_list",
                "pairs": [
                    {
                        "word": "string",
                        "translation": "string",
                    }
                ],
            },
            "test": {
                "type": "test",
                "questions": [
                    {
                        "question": "Markdown + LaTeX question",
                        "options": [
                            {
                                "option": "string",
                                "is_correct": True,
                            }
                        ],
                    }
                ],
            },
            "true_or_false": {
                "type": "true_or_false",
                "statements": [
                    {
                        "statement": "Markdown + LaTeX statement",
                        "is_true": True,
                    }
                ],
            },
            "fill_gaps": {
                "type": "fill_gaps",
                "mode": "open | closed",
                "text": "Text with gaps marked as ___",
                "answers": ["answer 1", "answer 2"],
            },
            "image": {
                "type": "image",
                "detailed_description": "string",
            },
            "match_cards": {
                "type": "match_cards",
                "pairs": [
                    {
                        "left": "string",
                        "right": "string",
                    }
                ],
            },
            "audio": {
                "type": "audio",
                "audio_type": "monologue | dialogue",
                "script": [
                    {
                        "speaker": "string",
                        "text": "string",
                    }
                ],
            },
        },
        "response_schema": {
            "sections": [
                {
                    "title": "string",
                    "tasks": [
                        {
                            "type": "task type from plan",
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


def count_gaps(text: str) -> int:
    return len(re.findall(r"___", text))


def validate_test_task(task: dict[str, Any]) -> tuple[bool, Optional[str]]:
    for question in task["questions"]:
        correct_count = sum(1 for option in question["options"] if option["is_correct"])

        if correct_count != 1:
            return False, "Each test question must have exactly one correct option"

    return True, None


def validate_fill_gaps_task(task: dict[str, Any]) -> tuple[bool, Optional[str]]:
    gaps_count = count_gaps(task["text"])

    if gaps_count == 0:
        return False, "fill_gaps.text must contain at least one gap marked as ___"

    if gaps_count < 4 or gaps_count > 10:
        return False, "fill_gaps must contain 4-10 gaps", None

    if gaps_count != len(task["answers"]):
        return False, "fill_gaps answers count must match gaps count"

    for answer in task["answers"]:
        if not isinstance(answer, str) or not answer.strip():
            return False, "fill_gaps answers cannot be empty"

    return True, None


def validate_audio_task(task: dict[str, Any]) -> tuple[bool, Optional[str]]:
    if task["audio_type"] == "monologue":
        if len(task["script"]) != 1:
            return False, "Monologue audio must have exactly one script replica"

        return True, None

    if len(task["script"]) < 4:
        return False, "Dialogue audio must have at least 4 script replicas"

    speakers = {replica["speaker"] for replica in task["script"]}

    if len(speakers) < 2:
        return False, "Dialogue audio must have at least 2 speakers"

    return True, None


def validate_generated_task(task: dict[str, Any]) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    try:
        parsed_task = GeneratedTaskAdapter.validate_python(task)
    except ValidationError as error:
        return False, str(error), None

    task_data = parsed_task.model_dump()

    if task_data["type"] == "test":
        is_valid, error_message = validate_test_task(task_data)

        if not is_valid:
            return False, error_message, None

    if task_data["type"] == "fill_gaps":
        is_valid, error_message = validate_fill_gaps_task(task_data)

        if not is_valid:
            return False, error_message, None

    if task_data["type"] == "audio":
        is_valid, error_message = validate_audio_task(task_data)

        if not is_valid:
            return False, error_message, None

    return True, None, task_data


def validate_tasks_result(
    data: dict[str, Any],
    request_data: GenerateTasksRequest,
) -> tuple[bool, Optional[str], Optional[list[dict[str, Any]]]]:
    if "sections" not in data:
        return False, "Missing field: sections", None

    if not isinstance(data["sections"], list):
        return False, "sections must be a list", None

    if len(data["sections"]) != len(request_data.sections):
        return False, "sections count mismatch", None

    generated_sections = []

    for section_index, section_data in enumerate(data["sections"]):
        if not isinstance(section_data, dict):
            return False, "Each section must be an object", None

        source_section = request_data.sections[section_index]

        if section_data.get("title") != source_section.title:
            return False, "Section title mismatch", None

        tasks = section_data.get("tasks")

        if not isinstance(tasks, list):
            return False, "tasks must be a list", None

        if len(tasks) != len(source_section.tasks):
            return False, "tasks count mismatch", None

        generated_tasks = []

        for task_index, task in enumerate(tasks):
            if not isinstance(task, dict):
                return False, "Each task must be an object", None

            expected_type = source_section.tasks[task_index].type
            actual_type = task.get("type")

            if actual_type != expected_type:
                return False, f"Task type mismatch: expected {expected_type}, got {actual_type}", None

            is_valid, error_message, generated_task = validate_generated_task(task)

            if not is_valid or not generated_task:
                return False, error_message, None

            generated_tasks.append(generated_task)

        generated_sections.append({
            "title": source_section.title,
            "reference": source_section.reference.model_dump(),
            "tasks": generated_tasks,
        })

    return True, None, generated_sections


def generate_tasks(request_data: GenerateTasksRequest) -> dict[str, Any]:
    settings = get_settings()
    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_tasks_prompt(
            request_data=request_data,
            previous_error=previous_error,
        )

        result = generate(prompt=prompt, model_type="pro")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, sections = validate_tasks_result(
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
        "message": previous_error or "Could not generate valid tasks",
    }