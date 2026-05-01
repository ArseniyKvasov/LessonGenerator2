from app.groq_client import extract_retry_after_seconds
from app.services.validators import (
    materialize_fill_gaps_text,
    validate_fill_gaps_task,
    validate_generated_task,
    validate_vocab_fill_gaps,
)


def test_fill_gaps_rejects_ambiguous_answer_variants() -> None:
    is_valid, error = validate_fill_gaps_task(
        {
            "type": "fill_gaps",
            "mode": "closed",
            "text": "1. I ___ (read).\n2. She ___ (play).\n3. They ___ (run).\n4. We ___ (write).",
            "answers": ["am reading / read", "is playing", "are running", "are writing"],
        }
    )

    assert not is_valid
    assert error == "fill_gaps answers must avoid multiple acceptable variants in one answer"


def test_fill_gaps_requires_4_to_10_gaps() -> None:
    is_valid, error = validate_fill_gaps_task(
        {
            "type": "fill_gaps",
            "mode": "closed",
            "text": "1. I ___ (read).\n2. She ___ (play).\n3. They ___ (run).",
            "answers": ["am reading", "is playing", "are running"],
        }
    )

    assert not is_valid
    assert "4-10 gaps" in error


def test_vocabulary_fill_gaps_rejects_words_outside_list() -> None:
    is_valid, error = validate_vocab_fill_gaps(
        {
            "type": "fill_gaps",
            "mode": "open",
            "text": (
                "1. The train is ___.\n"
                "2. I lost my ___.\n"
                "3. Go to the ___.\n"
                "4. Check the ___."
            ),
            "answers": ["late", "ticket", "platform", "gate"],
        },
        ["ticket", "platform", "delay", "gate"],
    )

    assert not is_valid
    assert "outside the list" in error


def test_test_task_requires_single_correct_option() -> None:
    is_valid, error, _ = validate_generated_task(
        {
            "type": "test",
            "questions": [
                {
                    "question": "Choose one.",
                    "options": [
                        {"option": "A", "is_correct": True},
                        {"option": "B", "is_correct": True},
                    ],
                },
                {
                    "question": "Choose two.",
                    "options": [
                        {"option": "A", "is_correct": True},
                        {"option": "B", "is_correct": False},
                    ],
                },
                {
                    "question": "Choose three.",
                    "options": [
                        {"option": "A", "is_correct": True},
                        {"option": "B", "is_correct": False},
                    ],
                },
            ],
        }
    )

    assert not is_valid
    assert error == "Each test question must have exactly one correct option"


def test_fill_gaps_text_is_materialized_in_answer_order() -> None:
    text = "He ___ (cook) dinner now.\nThey ___ (study) at home.\nI ___ (drink) tea.\nWe ___ (wait) outside."
    answers = ["is cooking", "are studying", "am drinking", "are waiting"]

    parsed = materialize_fill_gaps_text(text, answers)

    assert parsed == (
        "He {{is cooking}} (cook) dinner now.\n"
        "They {{are studying}} (study) at home.\n"
        "I {{am drinking}} (drink) tea.\n"
        "We {{are waiting}} (wait) outside."
    )


def test_generated_fill_gaps_contains_materialized_gaps() -> None:
    is_valid, error, parsed = validate_generated_task(
        {
            "type": "fill_gaps",
            "mode": "closed",
            "text": (
                "He ___ (cook) dinner now.\n"
                "They ___ (study) at home.\n"
                "I ___ (drink) tea.\n"
                "We ___ (wait) outside."
            ),
            "answers": ["is cooking", "are studying", "am drinking", "are waiting"],
        }
    )

    assert is_valid, error
    assert parsed is not None
    assert "{{is cooking}}" in parsed["text"]
    assert "{{are waiting}}" in parsed["text"]


def test_extracts_groq_retry_time_from_composite_message() -> None:
    seconds = extract_retry_after_seconds("Rate limit reached. Please try again in 34m3.36s. Need more tokens?")

    assert seconds == 2043.36
