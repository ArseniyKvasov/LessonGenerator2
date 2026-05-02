import random
import re
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

from app.schemas import GeneratedTask, LessonSection, TestTask


GeneratedTaskAdapter = TypeAdapter(GeneratedTask)
LessonSectionAdapter = TypeAdapter(LessonSection)
GAP_PATTERN = re.compile(r"_{3,}")
MARKDOWN_HEADING_PATTERN = re.compile(r"^\s*#+\s+(.+?)\s*#*\s*$")


def count_gaps(text: str) -> int:
    return len(GAP_PATTERN.findall(text))


def materialize_fill_gaps_text(text: str, answers: list[str]) -> str:
    answer_index = 0

    def replacer(_: re.Match[str]) -> str:
        nonlocal answer_index
        value = answers[answer_index]
        answer_index += 1
        return f"{{{{{value}}}}}"

    return GAP_PATTERN.sub(replacer, text)


def normalize_markdown_headings(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        match = MARKDOWN_HEADING_PATTERN.match(line)
        if not match:
            lines.append(line)
            continue

        title = match.group(1).strip()
        if title:
            lines.extend(["", f"**{title}**", ""])

    return "\n".join(lines).strip()


def shuffle_test_options(task: dict[str, Any]) -> dict[str, Any]:
    for question in task["questions"]:
        random.shuffle(question["options"])
    return task


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
    normalized_answers = [answer.strip().casefold() for answer in task["answers"]]
    if task["mode"] == "open" and len(normalized_answers) != len(set(normalized_answers)):
        return False, "open fill_gaps answers must be distinct"

    for answer in task["answers"]:
        if not isinstance(answer, str) or not answer.strip():
            return False, "fill_gaps answers cannot be empty"
        if "/" in answer or "," in answer:
            return False, "fill_gaps answers must avoid multiple acceptable variants in one answer"

    return True, None


def validate_vocab_fill_gaps(task: dict[str, Any], words: list[str]) -> tuple[bool, Optional[str]]:
    allowed = {word.casefold() for word in words}
    answers = {answer.casefold() for answer in task.get("answers", [])}
    invalid = sorted(answer for answer in answers if answer not in allowed)

    if invalid:
        return False, f"Vocabulary fill_gaps uses words outside the list: {', '.join(invalid)}"

    if task.get("mode") != "open":
        return False, "Vocabulary fill_gaps must use open mode"

    return True, None


def validate_audio_task(task: dict[str, Any]) -> tuple[bool, Optional[str]]:
    script_text = "\n".join(item["text"] for item in task["script"])
    if len(script_text) > 3000:
        return False, "Listening script must be 3000 characters or fewer"

    if task["audio_type"] == "monologue" and len(task["script"]) != 1:
        return False, "Monologue audio must have exactly one script item"

    if task["audio_type"] == "dialogue":
        speakers = {item["speaker"] for item in task["script"]}
        if len(speakers) < 2:
            return False, "Dialogue audio must have at least two speakers"

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
        task_data = shuffle_test_options(task_data)

    if task_data["type"] == "fill_gaps":
        is_valid, error_message = validate_fill_gaps_task(task_data)
        if not is_valid:
            return False, error_message, None
        task_data["text"] = materialize_fill_gaps_text(task_data["text"], task_data["answers"])
        task_data["text"] = normalize_markdown_headings(task_data["text"])

    if task_data["type"] == "note":
        task_data["content"] = normalize_markdown_headings(task_data["content"])

    if task_data["type"] == "audio":
        is_valid, error_message = validate_audio_task(task_data)
        if not is_valid:
            return False, error_message, None

    return True, None, task_data


def validate_section(section: dict[str, Any]) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    try:
        parsed_section = LessonSectionAdapter.validate_python(section)
    except ValidationError as error:
        return False, str(error), None

    return True, None, parsed_section.model_dump()
