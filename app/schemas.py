from typing import Any, Literal, Annotated, Union, Optional

from pydantic import BaseModel, Field, field_validator


class GenerateMetaRequest(BaseModel):
    user_request: str = Field(min_length=1)
    subjects_available: list[str]
    colors_available: list[str]
    icons_available: list[str]

    @field_validator("user_request")
    @classmethod
    def validate_user_request(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("user_request cannot be empty")

        return cleaned

    @field_validator(
        "subjects_available",
        "colors_available",
        "icons_available",
    )
    @classmethod
    def validate_available_values(
        cls,
        values: list[str],
    ) -> list[str]:
        if not values:
            raise ValueError("List cannot be empty")

        cleaned_values = [
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        ]

        if not cleaned_values:
            raise ValueError("List cannot contain only empty values")

        return cleaned_values


class GenerateMetaSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    topic: str
    subject: str
    color: str
    icon: str


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str


class GenerateSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: dict[str, Any]


class GenerateErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str


class SectionSchema(BaseModel):
    title: str = Field(min_length=1, max_length=40)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Section title cannot be empty")

        return cleaned


class GenerateSectionsRequest(BaseModel):
    user_request: str = Field(min_length=1)

    @field_validator("user_request")
    @classmethod
    def validate_user_request(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("user_request cannot be empty")

        return cleaned


class ImproveSectionRequest(BaseModel):
    user_request: str = Field(min_length=1)
    sections: list[SectionSchema] = Field(min_length=1)
    improvement_request: str = Field(min_length=1)

    @field_validator("user_request", "improvement_request")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Field cannot be empty")

        return cleaned


class GenerateSectionsSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    sections: list[SectionSchema]


class ImproveSectionSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    sections: list[SectionSchema]


class SectionReference(BaseModel):
    section_goal: str
    points: list[str]
    practice_focus: str


class SectionWithReference(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    reference: SectionReference

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Section title cannot be empty")

        return cleaned


class GenerateReferencesRequest(BaseModel):
    user_request: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    sections: list[SectionSchema]

    @field_validator("user_request", "topic")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Field cannot be empty")

        return cleaned


class GenerateSectionReferenceRequest(BaseModel):
    user_request: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    section: SectionSchema

    @field_validator("user_request", "topic")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Field cannot be empty")

        return cleaned


class GenerateReferencesSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    sections: list[SectionWithReference]


TaskType = Literal[
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


class TaskPlanItem(BaseModel):
    type: TaskType

    purpose: str = Field(min_length=1)

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("purpose cannot be empty")

        return cleaned


class SectionTaskPlan(BaseModel):
    title: str = Field(min_length=1, max_length=40)

    reference: SectionReference

    tasks: list[TaskPlanItem]


class GenerateTasksPlanRequest(BaseModel):
    lesson_topic: str = Field(min_length=1)
    sections: list[SectionWithReference] = Field(min_length=1)

    @field_validator("lesson_topic")
    @classmethod
    def validate_lesson_topic(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("lesson_topic cannot be empty")

        return cleaned


class GenerateSectionTasksPlanRequest(BaseModel):
    lesson_topic: str = Field(min_length=1)
    section: SectionWithReference


class GenerateTasksPlanSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"

    sections: list[SectionTaskPlan]


class NoteTask(BaseModel):
    type: Literal["note"]
    content: str = Field(
        min_length=1,
        description=(
            "Explanation text in Russian by default (unless explicitly requested otherwise). "
            "Supports Markdown, LaTeX and \\n for line breaks."
        ),
    )


class ReadingTextTask(BaseModel):
    type: Literal["reading_text"]
    content: str = Field(
        min_length=1,
        description="Reading text supports Markdown and \\n for line breaks.",
    )


class WordPair(BaseModel):
    word: str = Field(
        min_length=1,
        description="Word or phrase in source language.",
    )
    translation: str = Field(
        min_length=1,
        description="Russian translation for the word or phrase.",
    )


class WordListTask(BaseModel):
    type: Literal["word_list"]
    pairs: list[WordPair] = Field(min_length=3, max_length=20)


class TestOption(BaseModel):
    option: str = Field(min_length=1)
    is_correct: bool


class TestQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[TestOption] = Field(min_length=2, max_length=4)


class TestTask(BaseModel):
    type: Literal["test"]
    questions: list[TestQuestion] = Field(min_length=3, max_length=6)


class TrueFalseStatement(BaseModel):
    statement: str = Field(min_length=1)
    is_true: bool


class TrueFalseTask(BaseModel):
    type: Literal["true_or_false"]
    statements: list[TrueFalseStatement] = Field(min_length=3, max_length=8)


class FillGapsTask(BaseModel):
    type: Literal["fill_gaps"]
    mode: Literal["open", "closed"]
    text: str = Field(
        min_length=1,
        description="Text with gaps marked as ___; supports Markdown, LaTeX and \\n for line breaks.",
    )
    answers: list[str] = Field(min_length=1)


class ImageTask(BaseModel):
    type: Literal["image"]
    detailed_description: str = Field(min_length=1)


class MatchPair(BaseModel):
    left: str = Field(min_length=1)
    right: str = Field(min_length=1)


class MatchCardsTask(BaseModel):
    type: Literal["match_cards"]
    pairs: list[MatchPair] = Field(min_length=3, max_length=12)


class AudioReplica(BaseModel):
    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)


class AudioTask(BaseModel):
    type: Literal["audio"]
    audio_type: Literal["monologue", "dialogue"]
    script: list[AudioReplica] = Field(min_length=1)


class SpeakingCardsTask(BaseModel):
    type: Literal["speaking_cards"]
    speaking_cards: list[str] = Field(min_length=3, max_length=20)


class WordsToPronounceItem(BaseModel):
    sound: str = Field(min_length=1)
    words: list[str] = Field(min_length=1, max_length=20)


class WordsToPronounceTask(BaseModel):
    type: Literal["words_to_pronounce"]
    words_to_pronounce: list[WordsToPronounceItem] = Field(min_length=1, max_length=12)


GeneratedTask = Annotated[
    Union[
        NoteTask,
        ReadingTextTask,
        WordListTask,
        TestTask,
        TrueFalseTask,
        FillGapsTask,
        ImageTask,
        MatchCardsTask,
        AudioTask,
        SpeakingCardsTask,
        WordsToPronounceTask,
    ],
    Field(discriminator="type"),
]


class SectionWithGeneratedTasks(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    tasks: list[GeneratedTask] = Field(min_length=1)


class GenerateTasksRequest(BaseModel):
    lesson_topic: str = Field(min_length=1)
    section_title: str = Field(min_length=1, max_length=40)
    reference_points: list[str] = Field(min_length=1)
    tasks: list[TaskPlanItem] = Field(min_length=1)

    @field_validator("lesson_topic", "section_title")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Field cannot be empty")

        return cleaned

    @field_validator("reference_points")
    @classmethod
    def validate_reference_points(cls, values: list[str]) -> list[str]:
        cleaned_values = [
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        ]

        if not cleaned_values:
            raise ValueError("reference_points cannot be empty")

        return cleaned_values


class GenerateTasksSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    section: SectionWithGeneratedTasks
    

class GenerateImageRequest(BaseModel):
    detailed_description: str = Field(min_length=1)
    size: str = "1024x1024"
    quality: Literal["low", "medium", "high", "hd"] = "medium"
    response_format: Literal["url", "b64_json"] = "b64_json"

    @field_validator("detailed_description")
    @classmethod
    def validate_detailed_description(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("detailed_description cannot be empty")

        return cleaned


class GenerateImageSuccessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    response_format: Literal["url", "b64_json"]
    image: str


class AudioScriptItem(BaseModel):
    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)


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
