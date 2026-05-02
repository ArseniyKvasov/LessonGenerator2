import re
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


PracticalSkillType = Literal["reading", "listening", "writing", "speaking", "pronunciation"]
TaskType = Literal[
    "note",
    "word_list",
    "fill_gaps",
    "match_cards",
    "test",
    "true_false",
    "text_input",
    "image",
    "audio",
    "speaking_cards",
]
JobStatus = Literal["queued", "running", "done", "error"]


def _clean_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Field cannot be empty")
    return cleaned


def _clean_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("Expected a list")

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item:
            continue
        key = item.casefold()
        if key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


def _clean_grammar_list(values: Any) -> list[dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("Expected a list")

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            topic = value.strip()
            points = [topic] if topic else []
        elif isinstance(value, dict):
            raw_topic = value.get("topic")
            raw_points = value.get("points")
            if not isinstance(raw_topic, str):
                continue
            topic = raw_topic.strip()
            points = _clean_string_list(raw_points)
        else:
            continue

        if not topic:
            continue

        key = topic.casefold()
        if key in seen:
            continue
        cleaned.append({"topic": topic, "points": points or [topic]})
        seen.add(key)

    return cleaned


def topic_word_count(topic: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-я0-9]+(?:[-'][A-Za-zА-Яа-я0-9]+)?", topic))


def validate_topic(value: str) -> str:
    cleaned = _clean_text(value)
    words = topic_word_count(cleaned)
    if words < 2 or words > 4:
        raise ValueError("topic must contain 2-4 words")
    return cleaned


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str


class JobCreateResponse(BaseModel):
    status: Literal["queued"] = "queued"
    job_id: str
    job_type: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: Optional[str] = None
    status: JobStatus
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    models_available: bool


DEFAULT_PRACTICAL_SKILL_TITLES: dict[str, str] = {
    "reading": "Reading Text",
    "listening": "Listening Practice",
    "writing": "Writing Task",
    "speaking": "Speaking Practice",
    "pronunciation": "Pronunciation Sounds",
}


class PracticalSkillItem(BaseModel):
    type: PracticalSkillType
    title: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_text(value)


class GrammarItem(BaseModel):
    topic: str = Field(min_length=1)
    points: list[str] = Field(min_length=1, max_length=4)

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("points", mode="before")
    @classmethod
    def clean_points(cls, values: Any) -> list[str]:
        return _clean_string_list(values)


class LessonBrief(BaseModel):
    lesson_goal: str = Field(min_length=1)
    vocabulary: list[str] = Field(default_factory=list)
    grammar: list[GrammarItem] = Field(default_factory=list)
    practical_skills: list[PracticalSkillItem] = Field(default_factory=list)

    @field_validator("lesson_goal")
    @classmethod
    def validate_goal(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("vocabulary", mode="before")
    @classmethod
    def clean_lists(cls, values: Any) -> list[str]:
        return _clean_string_list(values)

    @field_validator("grammar", mode="before")
    @classmethod
    def clean_grammar(cls, values: Any) -> list[dict[str, Any]]:
        return _clean_grammar_list(values)

    @field_validator("practical_skills", mode="before")
    @classmethod
    def clean_skills(cls, values: Any) -> list[dict[str, str]]:
        if values is None:
            return []
        if not isinstance(values, list):
            raise ValueError("practical_skills must be a list")

        cleaned: list[dict[str, str]] = []
        seen: set[str] = set()
        for value in values:
            if isinstance(value, str):
                skill_type = value.strip()
                title = DEFAULT_PRACTICAL_SKILL_TITLES.get(skill_type, skill_type)
            elif isinstance(value, dict):
                raw_type = value.get("type")
                raw_title = value.get("title")
                if not isinstance(raw_type, str):
                    continue
                skill_type = raw_type.strip()
                title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else DEFAULT_PRACTICAL_SKILL_TITLES.get(skill_type, skill_type)
            else:
                continue

            if not skill_type:
                continue

            key = skill_type.casefold()
            if key in seen:
                continue
            cleaned.append({"type": skill_type, "title": title})
            seen.add(key)

        return cleaned


class GenerateBriefRequest(BaseModel):
    user_request: str = Field(min_length=1)

    @field_validator("user_request")
    @classmethod
    def validate_user_request(cls, value: str) -> str:
        return _clean_text(value)


class GenerateBriefSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    topic: str
    brief: LessonBrief

    @field_validator("topic")
    @classmethod
    def validate_response_topic(cls, value: str) -> str:
        return validate_topic(value)


class ImproveBriefRequest(BaseModel):
    topic: str
    brief: LessonBrief
    improvement_request: str = Field(min_length=1)

    @field_validator("topic")
    @classmethod
    def validate_request_topic(cls, value: str) -> str:
        return validate_topic(value)

    @field_validator("improvement_request")
    @classmethod
    def validate_improvement_request(cls, value: str) -> str:
        return _clean_text(value)


class ImproveBriefSuccessResponse(GenerateBriefSuccessResponse):
    pass


class GenerateStyleRequest(BaseModel):
    topic: str
    colors_available: list[str]
    icons_available: list[str]

    @field_validator("topic")
    @classmethod
    def validate_request_topic(cls, value: str) -> str:
        return validate_topic(value)

    @field_validator("colors_available", "icons_available", mode="before")
    @classmethod
    def validate_available_values(cls, values: Any) -> list[str]:
        cleaned = _clean_string_list(values)
        if not cleaned:
            raise ValueError("List cannot be empty")
        return cleaned


class GenerateStyleSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    color: str
    icon: str


class GenerateSectionsRequest(BaseModel):
    topic: str
    brief: LessonBrief

    @field_validator("topic")
    @classmethod
    def validate_request_topic(cls, value: str) -> str:
        return validate_topic(value)


class WordPair(BaseModel):
    word: str = Field(min_length=1)
    translation: str = Field(min_length=1)

    @field_validator("word", "translation")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        return _clean_text(value)


class WordListTask(BaseModel):
    type: Literal["word_list"]
    pairs: list[WordPair] = Field(min_length=1, max_length=20)


class FillGapsTask(BaseModel):
    type: Literal["fill_gaps"]
    mode: Literal["open", "closed"]
    text: str = Field(min_length=1)
    answers: list[str] = Field(min_length=1, max_length=12)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("answers", mode="before")
    @classmethod
    def clean_lists(cls, values: Any) -> list[str]:
        return _clean_string_list(values)


class MatchPair(BaseModel):
    left: str = Field(min_length=1)
    right: str = Field(min_length=1)

    @field_validator("left", "right")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        return _clean_text(value)


class MatchCardsTask(BaseModel):
    type: Literal["match_cards"]
    pairs: list[MatchPair] = Field(min_length=3, max_length=12)


class NoteTask(BaseModel):
    type: Literal["note"]
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return _clean_text(value)


class TestOption(BaseModel):
    option: str = Field(min_length=1)
    is_correct: bool

    @field_validator("option")
    @classmethod
    def validate_option(cls, value: str) -> str:
        return _clean_text(value)


class TestQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[TestOption] = Field(min_length=2, max_length=4)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        return _clean_text(value)


class TestTask(BaseModel):
    type: Literal["test"]
    questions: list[TestQuestion] = Field(min_length=1, max_length=7)


class TrueFalseStatement(BaseModel):
    statement: str = Field(min_length=1)
    is_true: bool

    @field_validator("statement")
    @classmethod
    def validate_statement(cls, value: str) -> str:
        return _clean_text(value)


class TrueFalseTask(BaseModel):
    type: Literal["true_false"]
    statements: list[TrueFalseStatement] = Field(min_length=3, max_length=6)


class TextInputTask(BaseModel):
    type: Literal["text_input"]
    title: str = Field(min_length=1, max_length=80)
    default_text: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_text(value)


class ImageTask(BaseModel):
    type: Literal["image"]
    detailed_description: str = Field(min_length=1)
    response_format: Literal["url", "b64_json"] = "b64_json"
    image: str = Field(min_length=1)

    @field_validator("detailed_description", "image")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        return _clean_text(value)


class AudioScriptItem(BaseModel):
    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("speaker", "text")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        return _clean_text(value)


class AudioTask(BaseModel):
    type: Literal["audio"]
    audio_type: Literal["monologue", "dialogue"]
    script: list[AudioScriptItem] = Field(min_length=1)
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    audio_base64: str = Field(min_length=1)


class SpeakingCardsTask(BaseModel):
    type: Literal["speaking_cards"]
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return _clean_text(value)


GeneratedTask = Annotated[
    Union[
        NoteTask,
        WordListTask,
        FillGapsTask,
        MatchCardsTask,
        TestTask,
        TrueFalseTask,
        TextInputTask,
        ImageTask,
        AudioTask,
        SpeakingCardsTask,
    ],
    Field(discriminator="type"),
]


class LessonSection(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    tasks: list[GeneratedTask] = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_text(value)


class GenerateSectionsSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    sections: list[LessonSection] = Field(min_length=1)


class GenerateImageRequest(BaseModel):
    detailed_description: str = Field(min_length=1)
    size: str = "1024x1024"
    quality: Literal["low", "medium", "high", "hd"] = "medium"
    response_format: Literal["url", "b64_json"] = "b64_json"

    @field_validator("detailed_description")
    @classmethod
    def validate_detailed_description(cls, value: str) -> str:
        return _clean_text(value)


class GenerateImageSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    response_format: Literal["url", "b64_json"]
    image: str


class GenerateAudioRequest(BaseModel):
    audio_type: Literal["monologue", "dialogue"]
    script: list[AudioScriptItem] = Field(min_length=1)
    voice: str = "nova"
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


class GenerateAudioSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]
    audio_base64: str
