import asyncio
import json
import math
import re
from typing import Any, Callable, Optional

from pydantic import ValidationError

from app.config import get_settings
from app.groq_client import generate
from app.schemas import (
    AudioScriptItem,
    GenerateAudioRequest,
    GenerateImageRequest,
    GenerateSectionsRequest,
    GenerateSectionsSuccessResponse,
    LessonSection,
)
from app.services.media_generator import build_audio_text, generate_audio_file, generate_image_file
from app.services.validators import validate_generated_task, validate_vocab_fill_gaps


JsonValidator = Callable[[dict[str, Any]], tuple[bool, Optional[str], Optional[Any]]]


def _dump_prompt(payload: dict[str, Any], previous_error: Optional[str]) -> str:
    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = "Regenerate the response and fix this validation error."
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _call_ai(
    prompt_builder: Callable[[Optional[str]], str],
    validator: JsonValidator,
    *,
    temperature: float = 0,
    max_tokens: Optional[int] = None,
) -> tuple[bool, Optional[str], Optional[Any]]:
    settings = get_settings()
    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        result = await generate(
            prompt=prompt_builder(previous_error),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, payload = validator(result["data"])
        if is_valid:
            return True, None, payload

        previous_error = error_message

    return False, previous_error, None


def _short_title(value: str, fallback: str = "Grammar") -> str:
    title = re.sub(r"[^A-Za-zА-Яа-я0-9+/' -]+", "", value).strip()
    if not title:
        return fallback
    return " ".join(title.split()[:4])[:60]


def _balanced_chunks(items: list[str], max_size: int = 12) -> list[list[str]]:
    if len(items) <= max_size:
        return [items]

    group_count = math.ceil(len(items) / max_size)
    while group_count > 1 and len(items) / group_count < 4:
        group_count -= 1

    base_size = len(items) // group_count
    remainder = len(items) % group_count
    chunks: list[list[str]] = []
    start = 0

    for index in range(group_count):
        size = base_size + (1 if index < remainder else 0)
        chunks.append(items[start : start + size])
        start += size

    return chunks


def _fallback_vocabulary_groups(vocabulary: list[str]) -> list[dict[str, Any]]:
    chunks = _balanced_chunks(vocabulary)
    if len(chunks) == 1:
        return [{"title": "Vocabulary", "words": chunks[0]}]

    return [
        {"title": f"Words {index + 1}", "words": chunk}
        for index, chunk in enumerate(chunks)
    ]


def build_vocabulary_groups_prompt(
    topic: str,
    vocabulary: list[str],
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "vocabulary": vocabulary,
        "task": "Split vocabulary into logically connected, balanced ESL groups.",
        "rules": [
            "Return only valid JSON.",
            "Use every vocabulary item exactly once.",
            "Do not add new vocabulary.",
            "Each group must contain 4-12 words or phrases.",
            "Groups must be balanced in size.",
            "Each title must be 1-2 words.",
        ],
        "response_schema": {
            "groups": [
                {"title": "string, 1-2 words", "words": ["exact input vocabulary item"]}
            ]
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_vocabulary_groups_factory(vocabulary: list[str]) -> JsonValidator:
    expected = {word.casefold(): word for word in vocabulary}

    def validator(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
        groups = data.get("groups")
        if not isinstance(groups, list) or not groups:
            return False, "groups must be a non-empty list", None

        seen: list[str] = []
        parsed_groups: list[dict[str, Any]] = []
        for group in groups:
            if not isinstance(group, dict):
                return False, "Each group must be an object", None
            title = group.get("title")
            words = group.get("words")
            if not isinstance(title, str) or not title.strip():
                return False, "Each group needs a title", None
            if len(title.split()) > 2:
                return False, "Vocabulary group titles must be 1-2 words", None
            if not isinstance(words, list) or len(words) < 4 or len(words) > 12:
                return False, "Each group must contain 4-12 words", None
            normalized_words = []
            for word in words:
                if not isinstance(word, str):
                    return False, "Vocabulary words must be strings", None
                key = word.casefold()
                if key not in expected:
                    return False, f"Unknown vocabulary item: {word}", None
                normalized_words.append(expected[key])
                seen.append(key)
            parsed_groups.append({"title": title.strip(), "words": normalized_words})

        if sorted(seen) != sorted(expected.keys()):
            return False, "Groups must use every vocabulary item exactly once", None

        return True, None, parsed_groups

    return validator


async def _split_vocabulary(topic: str, vocabulary: list[str]) -> list[dict[str, Any]]:
    if len(vocabulary) < 4:
        return []
    if len(vocabulary) <= 12:
        return [{"title": "Vocabulary", "words": vocabulary}]

    is_valid, _, groups = await _call_ai(
        lambda previous_error: build_vocabulary_groups_prompt(topic, vocabulary, previous_error),
        _validate_vocabulary_groups_factory(vocabulary),
        temperature=0,
    )
    if is_valid and groups:
        return groups

    return _fallback_vocabulary_groups(vocabulary)


def build_vocabulary_tasks_prompt(
    topic: str,
    words: list[str],
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "vocabulary": words,
        "task": "Generate ESL vocabulary tasks for this exact vocabulary group.",
        "rules": [
            "Return only valid JSON.",
            "Generate exactly three tasks in this order: word_list, fill_gaps, match_cards.",
            "word_list must map each exact English word or phrase to a Russian translation.",
            "fill_gaps must use mode=open.",
            "fill_gaps must contain 4-10 gaps marked as ____ or ___.",
            "fill_gaps must include \\n.",
            "One gap per sentence is recommended for clarity.",
            "fill_gaps answers must use only exact words or phrases from vocabulary.",
            "fill_gaps answers must be in the same order as gaps in the text.",
            "match_cards must use phrase matching or word-definition matching.",
            "Tasks must be useful for a one-on-one ESL lesson.",
        ],
        "response_schema": {
            "tasks": [
                {"type": "word_list", "pairs": [{"word": "exact vocabulary item", "translation": "Russian"}]},
                {"type": "fill_gaps", "mode": "open", "text": "Text with ___ gaps", "answers": ["exact vocabulary item in gap order"]},
                {"type": "match_cards", "pairs": [{"left": "word or phrase", "right": "definition or matching phrase"}]},
            ]
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_vocabulary_tasks_factory(words: list[str]) -> JsonValidator:
    expected = {word.casefold(): word for word in words}

    def validator(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
        tasks = data.get("tasks")
        if not isinstance(tasks, list) or len(tasks) != 3:
            return False, "Vocabulary section must contain exactly three tasks", None

        expected_types = ["word_list", "fill_gaps", "match_cards"]
        parsed_tasks: list[dict[str, Any]] = []
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                return False, "Each task must be an object", None
            if task.get("type") != expected_types[index]:
                return False, "Vocabulary tasks must be word_list, fill_gaps, match_cards", None

            is_valid, error_message, parsed = validate_generated_task(task)
            if not is_valid or not parsed:
                return False, error_message, None

            if parsed["type"] == "word_list":
                pair_words = [pair["word"].casefold() for pair in parsed["pairs"]]
                if sorted(pair_words) != sorted(expected.keys()):
                    return False, "word_list must contain every vocabulary item exactly once", None
                for pair in parsed["pairs"]:
                    pair["word"] = expected[pair["word"].casefold()]

            if parsed["type"] == "fill_gaps":
                is_vocab_valid, vocab_error = validate_vocab_fill_gaps(parsed, words)
                if not is_vocab_valid:
                    return False, vocab_error, None
                parsed["answers"] = [expected[answer.casefold()] for answer in parsed["answers"]]

            parsed_tasks.append(parsed)

        return True, None, parsed_tasks

    return validator


async def _generate_vocabulary_section(topic: str, group: dict[str, Any]) -> dict[str, Any]:
    words = group["words"]
    is_valid, error_message, tasks = await _call_ai(
        lambda previous_error: build_vocabulary_tasks_prompt(topic, words, previous_error),
        _validate_vocabulary_tasks_factory(words),
        temperature=0,
    )
    if not is_valid or not tasks:
        raise ValueError(error_message or "Could not generate valid vocabulary tasks")

    return {
        "title": group["title"],
        "tasks": tasks,
    }


def _fallback_grammar_sections(grammar: list[str]) -> list[dict[str, Any]]:
    if not grammar:
        return []

    return [
        {"title": _short_title(item), "points": [item]}
        for item in grammar
    ]


def build_grammar_sections_prompt(
    topic: str,
    grammar: list[str],
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "grammar": grammar,
        "task": "Decide whether the grammar should be split into multiple lesson sections before task generation.",
        "rules": [
            "Return only valid JSON.",
            "Use the examples only as decision examples, not as hard-coded rules.",
            "Example: Present Continuous may be split into signal words, affirmative, negative, questions, and mixed practice.",
            "Example: First Conditional may stay as one section or be split if the lesson scope needs it.",
            "If splitting is useful, return exactly the sections you recommend.",
            "If splitting is not useful, return one section per coherent grammar focus.",
            "Do not add unrelated grammar.",
            "Each section title must be short and classroom-friendly.",
            "Each points array must list the exact sub-points this section should teach or practice.",
        ],
        "response_schema": {
            "sections": [
                {
                    "title": "string",
                    "points": ["grammar point or sub-point"],
                }
            ]
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_grammar_sections_factory(grammar: list[str]) -> JsonValidator:
    def validator(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
        sections = data.get("sections")
        if not isinstance(sections, list) or not sections:
            return False, "sections must be a non-empty list", None
        if len(sections) > 10:
            return False, "Grammar plan must contain no more than 10 sections", None

        parsed_sections: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for section in sections:
            if not isinstance(section, dict):
                return False, "Each grammar section must be an object", None

            title = section.get("title")
            points = section.get("points")
            if not isinstance(title, str) or not title.strip():
                return False, "Each grammar section needs a title", None
            clean_title = _short_title(title)
            title_key = clean_title.casefold()
            if title_key in seen_titles:
                return False, "Grammar section titles must be unique", None
            seen_titles.add(title_key)

            if not isinstance(points, list) or not points:
                return False, "Each grammar section needs a non-empty points array", None

            clean_points: list[str] = []
            for point in points:
                if not isinstance(point, str) or not point.strip():
                    return False, "Grammar section points must be non-empty strings", None
                clean_points.append(point.strip())

            parsed_sections.append({"title": clean_title, "points": clean_points})

        return True, None, parsed_sections

    return validator


async def _split_grammar(topic: str, grammar: list[str]) -> list[dict[str, Any]]:
    if not grammar:
        return []

    is_valid, _, sections = await _call_ai(
        lambda previous_error: build_grammar_sections_prompt(topic, grammar, previous_error),
        _validate_grammar_sections_factory(grammar),
        temperature=0,
    )
    if is_valid and sections:
        return sections

    return _fallback_grammar_sections(grammar)


def build_grammar_tasks_prompt(
    topic: str,
    grammar_section: dict[str, Any],
    full_grammar: list[str],
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "grammar_section": grammar_section,
        "full_grammar": full_grammar,
        "task": "Generate ESL grammar support material and practice tasks for a tutor-led one-on-one lesson.",
        "rules": [
            "Return only valid JSON.",
            "Generate note, test, and fill_gaps tasks in this order.",
            "Add word_list only if absolutely necessary, for example signal words.",
            "note.content must be Markdown and must include \\n line breaks.",
            "note.content is support material for the tutor: minimal explanations, focus on examples, short comments only if necessary.",
            "test must be multiple choice with 4-7 short and clear questions with at least one correct option per question.",
            "fill_gaps must be closed.",
            "fill_gaps must contain 4-10 gaps marked as ____ or ___.",
            "One gap per sentence is recommended for clarity.",
            "fill_gaps answers must be in the same order as gaps in the text.",
            "For closed fill_gaps, include base words directly in text, for example: He ___ (cook) dinner now.",
            "Tasks must be relevant for ESL tutoring.",
        ],
        "response_schema": {
            "tasks": [
                {"type": "note", "content": "Markdown with \\n line breaks"},
                {"type": "test", "questions": [{"question": "string", "options": [{"option": "string", "is_correct": True}]}]},
                {"type": "fill_gaps", "mode": "closed", "text": "Text with ___ gaps and optional base words in parentheses", "answers": ["answer in gap order"]},
            ]
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_grammar_tasks(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) < 3 or len(tasks) > 4:
        return False, "Grammar section must contain 3-4 tasks", None

    required_types = ["note", "test", "fill_gaps"]
    parsed_tasks: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            return False, "Each task must be an object", None
        if index < 3 and task.get("type") != required_types[index]:
            return False, "Grammar tasks must start with note, test, fill_gaps", None
        if index == 3 and task.get("type") != "word_list":
            return False, "Only word_list may be added as a fourth grammar task", None

        is_valid, error_message, parsed = validate_generated_task(task)
        if not is_valid or not parsed:
            return False, error_message, None
        if parsed["type"] == "note" and "\n" not in parsed["content"]:
            return False, "Grammar note must include a line break", None
        if parsed["type"] == "fill_gaps" and parsed["mode"] != "closed":
            return False, "Grammar fill_gaps must be closed", None
        parsed_tasks.append(parsed)

    return True, None, parsed_tasks


async def _generate_grammar_section(topic: str, grammar_section: dict[str, Any], full_grammar: list[str]) -> dict[str, Any]:
    is_valid, error_message, tasks = await _call_ai(
        lambda previous_error: build_grammar_tasks_prompt(topic, grammar_section, full_grammar, previous_error),
        _validate_grammar_tasks,
        temperature=0,
    )
    if not is_valid or not tasks:
        raise ValueError(error_message or "Could not generate valid grammar tasks")

    return {
        "title": grammar_section["title"],
        "tasks": tasks,
    }


def _ensure_markdown_note(content: str) -> str:
    cleaned = content.strip()
    if "\n" not in cleaned:
        cleaned = f"{cleaned}\n"
    return cleaned


def build_reading_text_prompt(
    topic: str,
    brief: dict[str, Any],
    reading_title: str,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "brief": brief,
        "reading_title": reading_title,
        "task": "Generate a short ESL reading text for a one-on-one lesson.",
        "rules": [
            "Return only valid JSON.",
            "Use vocabulary and grammar from the brief, but only a small relevant part of them.",
            "Match the likely ESL level implied by the brief.",
            "Use Markdown and include at least one \\n line break.",
            "Use reading_title as the text heading.",
            "Do not add tasks here; generate only the text.",
        ],
        "response_schema": {"content": "Markdown reading text with \\n"},
    }
    return _dump_prompt(payload, previous_error)


def _validate_text_content(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        return False, "content must be a non-empty string", None
    return True, None, _ensure_markdown_note(content)


def _fallback_reading_text(topic: str, brief: dict[str, Any], reading_title: str) -> str:
    vocabulary = brief.get("vocabulary") or []
    grammar = brief.get("grammar") or []
    words = ", ".join(vocabulary[:4]) if vocabulary else "simple English phrases"
    grammar_focus = grammar[0] if grammar else "clear sentences"
    return (
        f"**{reading_title}**\n\n"
        f"Mira has a short English lesson today. She practices {words}. "
        f"Her tutor asks simple questions and helps her use {grammar_focus}. "
        "Mira answers slowly, checks her mistakes, and tries again. "
        "At the end, she can say her ideas more clearly."
    )


def build_comprehension_task_prompt(
    text: str,
    task_type: str,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "exact_text": text,
        "task_type": task_type,
        "task": "Generate comprehension questions using only the exact text provided.",
        "rules": [
            "Return only valid JSON.",
            "Do not use information outside exact_text.",
            "For test, generate 3-6 questions with exactly one correct option per question.",
            "For true_false, generate 3-6 statements.",
            "Do not shuffle answer options; the application will shuffle them programmatically.",
        ],
        "response_schema": {
            "task": {"type": task_type}
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_comprehension_task_factory(task_type: str) -> JsonValidator:
    def validator(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
        task = data.get("task")
        if not isinstance(task, dict):
            return False, "task must be an object", None
        if task.get("type") != task_type:
            return False, f"task.type must be {task_type}", None
        is_valid, error_message, parsed = validate_generated_task(task)
        if not is_valid or not parsed:
            return False, error_message, None
        return True, None, parsed

    return validator


def _fallback_comprehension_task(task_type: str) -> dict[str, Any]:
    if task_type == "test":
        task = {
            "type": "test",
            "questions": [
                {
                    "question": "What is the text mainly about?",
                    "options": [
                        {"option": "An English lesson", "is_correct": True},
                        {"option": "A train journey", "is_correct": False},
                        {"option": "A shopping list", "is_correct": False},
                    ],
                },
                {
                    "question": "Who helps the student?",
                    "options": [
                        {"option": "A tutor", "is_correct": True},
                        {"option": "A doctor", "is_correct": False},
                        {"option": "A driver", "is_correct": False},
                    ],
                },
                {
                    "question": "What does the student do with mistakes?",
                    "options": [
                        {"option": "Checks them and tries again", "is_correct": True},
                        {"option": "Ignores them", "is_correct": False},
                        {"option": "Stops the lesson", "is_correct": False},
                    ],
                },
            ],
        }
    else:
        task = {
            "type": "true_false",
            "statements": [
                {"statement": "The text is about an English lesson.", "is_true": True},
                {"statement": "The student never speaks in the lesson.", "is_true": False},
                {"statement": "The tutor helps the student improve.", "is_true": True},
            ],
        }

    _, _, parsed = validate_generated_task(task)
    return parsed or task


async def _generate_comprehension_task(text: str, task_type: str) -> dict[str, Any]:
    is_valid, _, task = await _call_ai(
        lambda previous_error: build_comprehension_task_prompt(text, task_type, previous_error),
        _validate_comprehension_task_factory(task_type),
        temperature=0,
    )
    return task if is_valid and task else _fallback_comprehension_task(task_type)


def _split_text_halves(text: str) -> tuple[str, str]:
    middle = len(text) // 2
    split_at = text.find(".", middle)
    if split_at == -1:
        split_at = middle
    first = text[: split_at + 1].strip()
    second = text[split_at + 1 :].strip() or text.strip()
    return first, second


async def _generate_comprehension_tasks(text: str, short_type: str = "test") -> list[dict[str, Any]]:
    if len(text) < 1000:
        return [await _generate_comprehension_task(text, short_type)]

    first, second = _split_text_halves(text)
    return await asyncio.gather(
        _generate_comprehension_task(first, "test"),
        _generate_comprehension_task(second, "true_false"),
    )


async def _generate_reading_section(topic: str, brief: dict[str, Any], reading_title: str) -> dict[str, Any]:
    is_valid, _, content = await _call_ai(
        lambda previous_error: build_reading_text_prompt(topic, brief, reading_title, previous_error),
        _validate_text_content,
        temperature=0.9,
    )
    reading_text = content if is_valid and content else _fallback_reading_text(topic, brief, reading_title)
    tasks = [{"type": "note", "content": reading_text}]
    tasks.extend(await _generate_comprehension_tasks(reading_text, short_type="test"))
    return {"title": reading_title, "tasks": tasks}


def build_listening_script_prompt(
    topic: str,
    brief: dict[str, Any],
    listening_title: str,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "brief": brief,
        "listening_title": listening_title,
        "task": "Generate a listening script for an ESL one-on-one lesson.",
        "rules": [
            "Return only valid JSON.",
            "Use vocabulary and grammar from the brief, but only a small relevant part of them.",
            "Match the likely ESL level implied by the brief.",
            "Script must be 3000 characters or fewer.",
            "Choose monologue or dialogue.",
            "For monologue, use one script item with speaker Narrator.",
            "For dialogue, use at least two speakers.",
            "Keep the script aligned with listening_title.",
            "Do not add comprehension tasks here.",
        ],
        "response_schema": {
            "audio_type": "monologue | dialogue",
            "script": [{"speaker": "string", "text": "string"}],
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_listening_script(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
    audio_type = data.get("audio_type")
    script = data.get("script")
    if audio_type not in {"monologue", "dialogue"}:
        return False, "audio_type must be monologue or dialogue", None
    if not isinstance(script, list) or not script:
        return False, "script must be a non-empty list", None

    try:
        parsed_script = [AudioScriptItem.model_validate(item).model_dump() for item in script]
    except ValidationError as error:
        return False, str(error), None

    text_length = len("\n".join(item["text"] for item in parsed_script))
    if text_length > 3000:
        return False, "script length must be 3000 characters or fewer", None
    if audio_type == "monologue" and len(parsed_script) != 1:
        return False, "monologue must have exactly one script item", None
    if audio_type == "dialogue" and len({item["speaker"] for item in parsed_script}) < 2:
        return False, "dialogue must have at least two speakers", None

    return True, None, {"audio_type": audio_type, "script": parsed_script}


def _script_to_markdown(audio_type: str, script: list[dict[str, str]]) -> str:
    if audio_type == "monologue":
        return _ensure_markdown_note(script[0]["text"])

    lines = [f"**{item['speaker']}:** {item['text']}" for item in script]
    return "\n".join(lines)


async def _generate_listening_section(topic: str, brief: dict[str, Any], listening_title: str) -> Optional[dict[str, Any]]:
    is_valid, _, payload = await _call_ai(
        lambda previous_error: build_listening_script_prompt(topic, brief, listening_title, previous_error),
        _validate_listening_script,
        temperature=0.9,
    )
    if not is_valid or not payload:
        return None

    audio_request = GenerateAudioRequest(
        audio_type=payload["audio_type"],
        script=[AudioScriptItem.model_validate(item) for item in payload["script"]],
        response_format="mp3",
    )

    try:
        audio_response = await asyncio.wait_for(
            generate_audio_file(audio_request),
            timeout=get_settings().AUDIO_GENERATION_TIMEOUT_SECONDS,
        )
    except Exception:
        return None

    if audio_response.get("status") != "ok" or not audio_response.get("audio_base64"):
        return None

    script_note = _script_to_markdown(payload["audio_type"], payload["script"])
    audio_text = build_audio_text(audio_request)
    tasks = [
        {"type": "note", "content": script_note},
        {
            "type": "audio",
            "audio_type": payload["audio_type"],
            "script": payload["script"],
            "response_format": audio_response["response_format"],
            "audio_base64": audio_response["audio_base64"],
        },
    ]
    tasks.extend(await _generate_comprehension_tasks(audio_text, short_type="true_false"))
    return {"title": listening_title, "tasks": tasks}


def build_writing_prompt(
    topic: str,
    brief: dict[str, Any],
    writing_title: str,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "writing_title": writing_title,
        "vocabulary": brief.get("vocabulary", []),
        "grammar": brief.get("grammar", []),
        "task": "Generate a writing task for a one-on-one ESL lesson.",
        "rules": [
            "Return only valid JSON.",
            "instruction must be one sentence.",
            "instruction must briefly list what must be included.",
            "Do not include examples.",
            "instruction must use Markdown and include at least one \\n line break.",
            "Use writing_title as the writing topic. Do not invent another title.",
        ],
        "response_schema": {"instruction": "Markdown string"},
    }
    return _dump_prompt(payload, previous_error)


def _validate_writing_payload(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
    instruction = data.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        return False, "instruction must be a non-empty string", None
    return True, None, {"instruction": _ensure_markdown_note(instruction)}


async def _generate_writing_section(topic: str, brief: dict[str, Any], writing_title: str) -> dict[str, Any]:
    is_valid, _, payload = await _call_ai(
        lambda previous_error: build_writing_prompt(topic, brief, writing_title, previous_error),
        _validate_writing_payload,
        temperature=0,
    )
    if not is_valid or not payload:
        payload = {
            "instruction": f"Write a short answer about **{writing_title}** and include the target vocabulary or grammar from the lesson.\n",
        }

    return {
        "title": writing_title,
        "tasks": [
            {"type": "note", "content": payload["instruction"]},
            {"type": "text_input", "title": writing_title, "default_text": ""},
        ],
    }


def build_speaking_prompt(
    topic: str,
    brief: dict[str, Any],
    speaking_title: str,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": topic,
        "speaking_title": speaking_title,
        "vocabulary": brief.get("vocabulary", []),
        "grammar": brief.get("grammar", []),
        "task": "Prepare a speaking task for a one-on-one ESL lesson.",
        "rules": [
            "Return only valid JSON.",
            "Choose either Option A image + speaking questions or Option B speaking questions only.",
            "Use an image only if it clearly supports the speaking task.",
            "Generate 3-5 speaking questions.",
            "Questions must help the student produce English using the lesson vocabulary or grammar.",
            "Keep the questions aligned with speaking_title.",
            "If use_image=true, image_description must be a detailed visual prompt.",
        ],
        "response_schema": {
            "use_image": True,
            "image_description": "string or null",
            "questions": ["Question 1"],
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_speaking_payload(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
    use_image = data.get("use_image")
    questions = data.get("questions")
    image_description = data.get("image_description")
    if not isinstance(use_image, bool):
        return False, "use_image must be boolean", None
    if not isinstance(questions, list) or len(questions) < 3 or len(questions) > 5:
        return False, "speaking questions must contain 3-5 items", None
    cleaned_questions = [question.strip() for question in questions if isinstance(question, str) and question.strip()]
    if len(cleaned_questions) != len(questions):
        return False, "all speaking questions must be non-empty strings", None
    if use_image and (not isinstance(image_description, str) or not image_description.strip()):
        return False, "image_description is required when use_image=true", None
    return True, None, {
        "use_image": use_image,
        "image_description": image_description.strip() if isinstance(image_description, str) else None,
        "questions": cleaned_questions,
    }


def _speaking_cards_content(questions: list[str], has_image: bool) -> str:
    heading = "*Talk about the image*" if has_image else "*Read and answer the questions*"
    lines = [heading, ""]
    lines.extend(f"{index + 1}. {question}" for index, question in enumerate(questions))
    return "\n".join(lines)


async def _generate_speaking_section(topic: str, brief: dict[str, Any], speaking_title: str) -> dict[str, Any]:
    is_valid, _, payload = await _call_ai(
        lambda previous_error: build_speaking_prompt(topic, brief, speaking_title, previous_error),
        _validate_speaking_payload,
        temperature=0,
    )
    if not is_valid or not payload:
        payload = {
            "use_image": False,
            "image_description": None,
            "questions": [
                f"What can you say about {speaking_title}?",
                "Which words or grammar from the lesson can you use in your answer?",
                "Can you ask your tutor one question using today's language?",
            ],
        }

    tasks: list[dict[str, Any]] = []
    has_image = False
    if payload["use_image"]:
        image_request = GenerateImageRequest(
            detailed_description=payload["image_description"],
            response_format="b64_json",
        )
        image_response = await generate_image_file(image_request)
        if image_response.get("status") == "ok" and image_response.get("image"):
            has_image = True
            tasks.append(
                {
                    "type": "image",
                    "detailed_description": payload["image_description"],
                    "response_format": image_response["response_format"],
                    "image": image_response["image"],
                }
            )

    tasks.append(
        {
            "type": "speaking_cards",
            "content": _speaking_cards_content(payload["questions"], has_image=has_image),
        }
    )
    return {"title": speaking_title, "tasks": tasks}


def build_pronunciation_prompt(
    lesson_goal: str,
    vocabulary: list[str],
    target_sounds: str,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "lesson_goal": lesson_goal,
        "vocabulary": vocabulary,
        "target_sounds": target_sounds,
        "task": "Select relevant pronunciation sounds from the vocabulary for ESL practice.",
        "rules": [
            "Return only valid JSON.",
            "Use only words from vocabulary.",
            "Return sounds and words that are truly useful for pronunciation practice.",
            "Use target_sounds as the preferred sound focus whenever possible.",
            "Do not invent vocabulary.",
        ],
        "response_schema": {
            "sounds": [{"sound": "/i:/", "words": ["word from vocabulary"]}]
        },
    }
    return _dump_prompt(payload, previous_error)


def _validate_pronunciation_payload_factory(vocabulary: list[str]) -> JsonValidator:
    allowed = {word.casefold(): word for word in vocabulary}

    def validator(data: dict[str, Any]) -> tuple[bool, Optional[str], Optional[Any]]:
        sounds = data.get("sounds")
        if not isinstance(sounds, list) or not sounds:
            return False, "sounds must be a non-empty list", None
        parsed = []
        for item in sounds:
            if not isinstance(item, dict):
                return False, "each sound item must be an object", None
            sound = item.get("sound")
            words = item.get("words")
            if not isinstance(sound, str) or not sound.strip():
                return False, "sound must be a non-empty string", None
            if not isinstance(words, list) or not words:
                return False, "words must be a non-empty list", None
            normalized_words = []
            for word in words:
                if not isinstance(word, str):
                    return False, "pronunciation words must be strings", None
                key = word.casefold()
                if key not in allowed:
                    return False, f"pronunciation uses word outside vocabulary: {word}", None
                normalized_words.append(allowed[key])
            parsed.append({"sound": sound.strip(), "words": normalized_words})
        return True, None, parsed

    return validator


def _pronunciation_note(sounds: list[dict[str, Any]]) -> str:
    lines = ["*Practice these sounds*", ""]
    for item in sounds:
        lines.append(f"*{item['sound']}* - {', '.join(item['words'])}")
    return "\n".join(lines)


async def _generate_pronunciation_section(lesson_goal: str, vocabulary: list[str], target_sounds: str) -> Optional[dict[str, Any]]:
    if not vocabulary:
        return None
    is_valid, _, sounds = await _call_ai(
        lambda previous_error: build_pronunciation_prompt(lesson_goal, vocabulary, target_sounds, previous_error),
        _validate_pronunciation_payload_factory(vocabulary),
        temperature=0,
    )
    if not is_valid or not sounds:
        return None
    return {"title": target_sounds, "tasks": [{"type": "note", "content": _pronunciation_note(sounds)}]}


def _section_or_none(section: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not section:
        return None
    try:
        return LessonSection.model_validate(section).model_dump()
    except ValidationError:
        return None


async def generate_sections(request_data: GenerateSectionsRequest) -> dict[str, Any]:
    topic = request_data.topic
    brief = request_data.brief.model_dump()
    sections: list[dict[str, Any]] = []

    try:
        vocabulary_groups = await _split_vocabulary(topic, request_data.brief.vocabulary)
        section_tasks = [
            _generate_vocabulary_section(topic, group)
            for group in vocabulary_groups
        ]

        grammar_sections = await _split_grammar(topic, request_data.brief.grammar)
        section_tasks.extend(
            _generate_grammar_section(topic, grammar_section, request_data.brief.grammar)
            for grammar_section in grammar_sections
        )

        skill_titles = {
            skill.type: skill.title
            for skill in request_data.brief.practical_skills
        }
        if "reading" in skill_titles:
            section_tasks.append(_generate_reading_section(topic, brief, skill_titles["reading"]))

        if "listening" in skill_titles:
            section_tasks.append(_generate_listening_section(topic, brief, skill_titles["listening"]))

        if "writing" in skill_titles:
            section_tasks.append(_generate_writing_section(topic, brief, skill_titles["writing"]))

        if "speaking" in skill_titles:
            section_tasks.append(_generate_speaking_section(topic, brief, skill_titles["speaking"]))

        if "pronunciation" in skill_titles:
            section_tasks.append(
                _generate_pronunciation_section(
                    request_data.brief.lesson_goal,
                    request_data.brief.vocabulary,
                    skill_titles["pronunciation"],
                )
            )

        generated_sections = await asyncio.gather(*section_tasks)
        sections.extend(section for section in generated_sections if section)
    except ValueError as error:
        return {
            "status": "error",
            "message": str(error),
        }

    parsed_sections = [section for section in (_section_or_none(section) for section in sections) if section]

    if not parsed_sections:
        parsed_sections = [
            LessonSection(
                title="Speaking",
                tasks=[
                    {
                        "type": "speaking_cards",
                        "content": _speaking_cards_content(
                            [
                                f"What do you already know about {topic}?",
                                "Which part feels useful for real communication?",
                                "What would you like to practice with your tutor?",
                            ],
                            has_image=False,
                        ),
                    }
                ],
            ).model_dump()
        ]

    response = GenerateSectionsSuccessResponse(sections=parsed_sections)
    return response.model_dump()
