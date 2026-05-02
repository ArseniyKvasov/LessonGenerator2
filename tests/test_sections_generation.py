import asyncio

from app.schemas import GenerateSectionsRequest, LessonBrief
from app.services import sections_generator


def test_generate_sections_runs_independent_sections_concurrently(monkeypatch) -> None:
    active_tasks = 0
    max_active_tasks = 0

    async def wait_and_return(title: str) -> dict:
        nonlocal active_tasks, max_active_tasks
        active_tasks += 1
        max_active_tasks = max(max_active_tasks, active_tasks)
        await asyncio.sleep(0.01)
        active_tasks -= 1
        return {"title": title, "tasks": [{"type": "note", "content": f"{title}\n"}]}

    async def split_vocabulary(topic: str, vocabulary: list[str]) -> list[dict]:
        return [
            {"title": "Vocabulary A", "words": vocabulary[:4]},
            {"title": "Vocabulary B", "words": vocabulary[4:]},
        ]

    async def split_grammar(topic: str, grammar: list[str]) -> list[dict]:
        return [
            {
                "title": item["topic"] if isinstance(item, dict) else getattr(item, "topic", item),
                "points": item["points"] if isinstance(item, dict) else getattr(item, "points", [item]),
            }
            for item in grammar
        ]

    async def generate_vocabulary_section(topic: str, group: dict) -> dict:
        return await wait_and_return(group["title"])

    async def generate_grammar_section(topic: str, grammar_section: dict, full_grammar: list[str]) -> dict:
        return await wait_and_return(grammar_section["title"])

    async def generate_reading_section(topic: str, brief: dict, reading_title: str) -> dict:
        return await wait_and_return(reading_title)

    async def generate_writing_section(topic: str, brief: dict, writing_title: str) -> dict:
        return await wait_and_return(writing_title)

    async def generate_speaking_section(topic: str, brief: dict, speaking_title: str) -> dict:
        return await wait_and_return(speaking_title)

    monkeypatch.setattr(sections_generator, "_split_vocabulary", split_vocabulary)
    monkeypatch.setattr(sections_generator, "_split_grammar", split_grammar)
    monkeypatch.setattr(sections_generator, "_generate_vocabulary_section", generate_vocabulary_section)
    monkeypatch.setattr(sections_generator, "_generate_grammar_section", generate_grammar_section)
    monkeypatch.setattr(sections_generator, "_generate_reading_section", generate_reading_section)
    monkeypatch.setattr(sections_generator, "_generate_writing_section", generate_writing_section)
    monkeypatch.setattr(sections_generator, "_generate_speaking_section", generate_speaking_section)

    request = GenerateSectionsRequest(
        topic="Travel English",
        brief=LessonBrief(
            lesson_goal="Practice travel English in practical situations.",
            vocabulary=["ticket", "platform", "delay", "gate", "train", "seat", "map", "station"],
            grammar=["Past Simple"],
            practical_skills=[
                {"type": "reading", "title": "Reading Practice"},
                {"type": "writing", "title": "Writing Practice"},
                {"type": "speaking", "title": "Speaking Practice"},
            ],
        ),
    )

    response = asyncio.run(sections_generator.generate_sections(request))

    assert response["status"] == "ok"
    assert max_active_tasks > 1
    assert [section["title"] for section in response["sections"]] == [
        "Vocabulary A",
        "Vocabulary B",
        "Past Simple",
        "Reading Practice",
        "Writing Practice",
        "Speaking Practice",
    ]


def test_generate_sections_passes_serializable_grammar(monkeypatch) -> None:
    seen_split_grammar = None
    seen_full_grammar = None

    async def split_vocabulary(topic: str, vocabulary: list[str]) -> list[dict]:
        return []

    async def split_grammar(topic: str, grammar: list[dict]) -> list[dict]:
        nonlocal seen_split_grammar
        seen_split_grammar = grammar
        return [{"title": grammar[0]["topic"], "points": grammar[0]["points"]}]

    async def generate_grammar_section(topic: str, grammar_section: dict, full_grammar: list[dict]) -> dict:
        nonlocal seen_full_grammar
        seen_full_grammar = full_grammar
        return {"title": grammar_section["title"], "tasks": [{"type": "note", "content": "Grammar note"}]}

    monkeypatch.setattr(sections_generator, "_split_vocabulary", split_vocabulary)
    monkeypatch.setattr(sections_generator, "_split_grammar", split_grammar)
    monkeypatch.setattr(sections_generator, "_generate_grammar_section", generate_grammar_section)

    request = GenerateSectionsRequest(
        topic="Grammar Practice",
        brief=LessonBrief(
            lesson_goal="Practice present continuous in simple sentences.",
            grammar=[{"topic": "Present Continuous", "points": ["form", "questions"]}],
        ),
    )

    response = asyncio.run(sections_generator.generate_sections(request))

    assert response["status"] == "ok"
    assert seen_split_grammar == [{"topic": "Present Continuous", "points": ["form", "questions"]}]
    assert seen_full_grammar == [{"topic": "Present Continuous", "points": ["form", "questions"]}]


def test_split_grammar_uses_ai_section_plan(monkeypatch) -> None:
    async def call_ai(prompt_builder, validator, **kwargs):
        is_valid, error, sections = validator(
            {
                "sections": [
                    {"title": "AI Section A", "points": ["AI point A"]},
                    {"title": "AI Section B", "points": ["AI point B"]},
                ]
            }
        )
        return is_valid, error, sections

    monkeypatch.setattr(sections_generator, "_call_ai", call_ai)

    sections = asyncio.run(sections_generator._split_grammar("Any Grammar", ["Present Continuous"]))

    assert sections == [
        {"title": "AI Section A", "points": ["AI point A"]},
        {"title": "AI Section B", "points": ["AI point B"]},
    ]


def test_grammar_tasks_accept_note_without_line_break() -> None:
    is_valid, error, tasks = sections_generator._validate_grammar_tasks(
        {
            "tasks": [
                {"type": "note", "content": "Use am, is, or are before the -ing verb."},
                {
                    "type": "test",
                    "questions": [
                        {
                            "question": "Choose the correct sentence.",
                            "options": [
                                {"option": "She is reading.", "is_correct": True},
                                {"option": "She are reading.", "is_correct": False},
                            ],
                        },
                        {
                            "question": "Choose the correct sentence.",
                            "options": [
                                {"option": "They are cooking.", "is_correct": True},
                                {"option": "They is cooking.", "is_correct": False},
                            ],
                        },
                        {
                            "question": "Choose the correct sentence.",
                            "options": [
                                {"option": "I am waiting.", "is_correct": True},
                                {"option": "I is waiting.", "is_correct": False},
                            ],
                        },
                    ],
                },
                {
                    "type": "fill_gaps",
                    "mode": "closed",
                    "text": "She ___ (read) now. They ___ (cook) dinner. I ___ (wait) here. He ___ (run) fast.",
                    "answers": ["is reading", "are cooking", "am waiting", "is running"],
                },
            ]
        }
    )

    assert is_valid is True
    assert error is None
    assert tasks[0]["content"] == "Use am, is, or are before the -ing verb."
