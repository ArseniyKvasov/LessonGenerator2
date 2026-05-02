import pytest
from pydantic import ValidationError

from app.schemas import GenerateStyleRequest, ImproveBriefRequest, LessonBrief
from app.services.brief_generator import build_brief_prompt, build_improve_brief_prompt
from app.services.sections_generator import (
    build_comprehension_task_prompt,
    build_grammar_sections_prompt,
    build_grammar_tasks_prompt,
    build_reading_text_prompt,
    build_vocabulary_tasks_prompt,
)
from app.services.style_generator import build_style_prompt


def test_brief_prompt_describes_new_json_only_brief_flow() -> None:
    prompt = build_brief_prompt("Grammar-only lesson on Present Continuous")

    assert "Return only valid JSON" in prompt
    assert "topic must contain 2-4 words" in prompt
    assert "grammar-only" in prompt
    assert "{type, title}" in prompt
    assert "practical_skills.type may include only" in prompt


def test_improve_brief_prompt_preserves_existing_skill_titles() -> None:
    prompt = build_improve_brief_prompt(
        ImproveBriefRequest(
            topic="Travel English",
            brief=LessonBrief(
                lesson_goal="Practice polite travel questions.",
                vocabulary=["ticket", "platform"],
                grammar=[],
                practical_skills=[{"type": "speaking", "title": "Station Role Play"}],
            ),
            improvement_request="add more vocabulary",
        )
    )

    assert "Only modify fields that are clearly requested" in prompt
    assert "Station Role Play" in prompt
    assert "add more vocabulary" in prompt


def test_practical_skill_title_validates_only_length_limit() -> None:
    brief = LessonBrief(
        lesson_goal="Practice travel English.",
        practical_skills=[{"type": "reading", "title": "A title with more than five normal words"}],
    )

    assert brief.practical_skills[0].title == "A title with more than five normal words"

    with pytest.raises(ValidationError):
        LessonBrief(
            lesson_goal="Practice travel English.",
            practical_skills=[{"type": "reading", "title": "x" * 101}],
        )


def test_reading_prompt_uses_brief_stage_title() -> None:
    prompt = build_reading_text_prompt(
        "Travel English",
        {"vocabulary": ["ticket"], "grammar": [], "practical_skills": []},
        "Lost Ticket",
    )

    assert "reading_title" in prompt
    assert "Lost Ticket" in prompt
    assert "Use reading_title as the text heading" in prompt


def test_vocabulary_tasks_prompt_uses_fixed_list_and_open_gaps() -> None:
    prompt = build_vocabulary_tasks_prompt("Travel English", ["ticket", "platform", "delay", "gate"])

    assert "fill_gaps must use mode=open" in prompt
    assert "line breaks" in prompt
    assert "use only exact words" in prompt
    assert "ticket" in prompt


def test_grammar_prompt_requires_closed_gaps_with_base_words_in_text() -> None:
    prompt = build_grammar_tasks_prompt(
        "Present Continuous",
        {"title": "Affirmative", "points": ["am/is/are + verb-ing"]},
        ["Present Continuous"],
    )

    assert "fill_gaps must be closed" in prompt
    assert "base words directly in text" in prompt
    assert "fill_gaps.text should include line breaks" in prompt
    assert "One gap per sentence is recommended" in prompt
    assert "minimal explanations" in prompt


def test_grammar_sections_prompt_asks_ai_to_decide_split_with_examples() -> None:
    prompt = build_grammar_sections_prompt("Present Continuous", ["Present Continuous"])

    assert "Decide whether the grammar should be split" in prompt
    assert "Use the examples only as decision examples" in prompt
    assert "Present Continuous may be split" in prompt
    assert "First Conditional may stay as one section" in prompt
    assert "return exactly the sections you recommend" in prompt


def test_comprehension_prompt_uses_exact_text() -> None:
    prompt = build_comprehension_task_prompt("A short text.", "test")

    assert "exact_text" in prompt
    assert "using only the exact text provided" in prompt


def test_style_prompt_restricts_color_and_icon_lists() -> None:
    prompt = build_style_prompt(
        GenerateStyleRequest(
            topic="Travel English",
            colors_available=["blue", "green"],
            icons_available=["plane", "book"],
        )
    )

    assert "exactly one value from colors_available" in prompt
    assert "plane" in prompt
