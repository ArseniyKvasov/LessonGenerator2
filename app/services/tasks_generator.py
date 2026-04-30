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
        "lesson_topic": request_data.lesson_topic,
        "section_title": request_data.section_title,
        "tasks": [task.model_dump() for task in request_data.tasks],
        "task": (
            "Generate full task content for this section. "
            "Use lesson_topic, section_title and the provided task plan. "
            "Return tasks exactly in the requested JSON format."
        ),
        "generation_focus": [
            "Generate only tasks for the provided section.",
            "Each task must follow its type and purpose.",
            "Use lesson_topic and section_title as the main context source.",
        ],
        "rules": [
            "Return only valid JSON.",
            "Do not add markdown outside JSON.",
            "Keep the same task order.",
            "Use lesson_topic and section_title to generate relevant and focused content.",
            "Do not include lesson_topic in the response.",
            "Use Russian for explanatory text. Do not translate examples into Russian if they have another language.",
            "note.content supports Markdown + LaTeX + \\n for line breaks.",
            "note should be short and include examples mostrly.",
            "reading_text.content should include Markdown + \\n for line breaks.",
            "word_list.pairs must be word/phrase -> Russian translation.",
            "word_list.pairs must contain 5-15 items.",
            "For vocabulary sections, word_list must stay consistent with lesson_topic and section_title.",
            "test.questions must have 4-7 questions.",
            "test question supports LaTeX.",
            "Each test question must have 2-4 options.",
            "Each test question must have exactly one correct option.",
            "true_or_false.statements must have 3-8 statements.",
            "true_or_false.statement supports LaTeX.",
            "fill_gaps.text supports Markdown + LaTeX + \\n for line breaks.",
            "fill_gaps.text must use ___ for every gap.",
            "fill_gaps.text must contain 4-10 gaps marked as ___.",
            "fill_gaps.answers must contain answers in the same order as gaps.",
            "fill_gaps.mode must be 'open' or 'closed'.",
            "Each gap (___) must have exactly ONE correct answer.",
            "fill_gaps.answers must contain exactly one answer per gap in the same order as they appear in the text.",
            "The number of answers must exactly match the number of gaps.",
            "Answers must be short (one word or a short fixed phrase).",
            "Answers must be unambiguous and have only one valid form.",
            "In 'open' mode, answers will be shown to the user as a shuffled answer bank, so all answers must be distinct and reusable independently.",
            "In 'closed' mode, answers are hidden from the user but must still be provided in the response.",
            "Do not create gaps where multiple answers could be logically correct.",
            "Each gap must clearly correspond to one specific answer from the answers list."
            "image must return detailed_description only.",
            "audio must return audio_type and script.",
            "audio.audio_type must be monologue or dialogue.",
            "audio.script must be an array of replicas with speaker and text.",
            "For monologue, use one replica with speaker Narrator.",
            "For dialogue, use at least 4 replicas and at least 2 speakers.",
            "speaking_cards must return speaking_cards as an array of short prompts.",
            "words_to_pronounce must return words_to_pronounce as an array of objects with sound and words.",
        ],
        "task_json_formats": {
            "note": {
                "type": "note",
                "content": "Markdown + LaTeX content with \\n line breaks; Russian by default",
            },
            "reading_text": {
                "type": "reading_text",
                "content": "Markdown content with \\n line breaks",
            },
            "word_list": {
                "type": "word_list",
                "pairs": [
                    {
                        "word": "word or phrase",
                        "translation": "Russian translation",
                    }
                ],
            },
            "test": {
                "type": "test",
                "questions": [
                    {
                        "question": "LaTeX question",
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
                        "statement": "LaTeX statement",
                        "is_true": True,
                    }
                ],
            },
            "fill_gaps": {
                "type": "fill_gaps",
                "mode": "open | closed",
                "text": "Text with \\n and gaps marked as ___",
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
            "speaking_cards": {
                "type": "speaking_cards",
                "speaking_cards": ["string"],
            },
            "words_to_pronounce": {
                "type": "words_to_pronounce",
                "words_to_pronounce": [
                    {
                        "sound": "string",
                        "words": ["string"],
                    }
                ],
            },
        },
        "response_schema": {
            "section_title": "string",
            "tasks": [
                {
                    "type": "task type from plan",
                }
            ],
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = (
            "Regenerate the response and fix this error. "
            "Return only valid JSON that matches the schema."
        )

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
        return False, "fill_gaps must contain 4-10 gaps"

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


def validate_generated_task(
    task: dict[str, Any],
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Validate one generated task through Pydantic schema and additional
    business rules that are difficult to express in the base schema.
    """
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
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Validate generated tasks for a single section.

    The function checks that the model returned tasks only for the requested
    section, preserved task order, and generated every task according to the
    requested type from the task plan.
    """
    if "section_title" not in data:
        return False, "Missing field: section_title", None

    if data["section_title"] != request_data.section_title:
        return False, "Section title mismatch", None

    if "tasks" not in data:
        return False, "Missing field: tasks", None

    tasks = data["tasks"]

    if not isinstance(tasks, list):
        return False, "tasks must be a list", None

    if len(tasks) != len(request_data.tasks):
        return False, "tasks count mismatch", None

    generated_tasks = []

    for task_index, task in enumerate(tasks):
        if not isinstance(task, dict):
            return False, "Each task must be an object", None

        expected_type = request_data.tasks[task_index].type
        actual_type = task.get("type")

        if actual_type != expected_type:
            return False, f"Task type mismatch: expected {expected_type}, got {actual_type}", None

        is_valid, error_message, generated_task = validate_generated_task(task)

        if not is_valid or not generated_task:
            return False, error_message, None

        generated_tasks.append(generated_task)

    return True, None, {
        "title": request_data.section_title,
        "tasks": generated_tasks,
    }


async def generate_tasks(request_data: GenerateTasksRequest) -> dict[str, Any]:
    settings = get_settings()
    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        prompt = build_tasks_prompt(
            request_data=request_data,
            previous_error=previous_error,
        )

        result = await generate(prompt=prompt, model_type="pro")

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, section = validate_tasks_result(
            data=result["data"],
            request_data=request_data,
        )

        if is_valid and section:
            return {
                "status": "ok",
                "section": section,
            }

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate valid section tasks",
    }
