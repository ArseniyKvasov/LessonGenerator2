import json
from typing import Any, Optional, Type

from pydantic import ValidationError

from app.config import get_settings
from app.groq_client import generate
from app.schemas import (
    GenerateBriefRequest,
    GenerateBriefSuccessResponse,
    ImproveBriefRequest,
    ImproveBriefSuccessResponse,
)
from app.utils.text import trim_to_words_limit


PRACTICAL_SKILL_TYPES = [
    "reading",
    "listening",
    "writing",
    "speaking",
    "pronunciation",
]

PRACTICAL_SKILL_SCHEMA = [
    {
        "type": "reading | listening | writing | speaking | pronunciation",
        "title": "short title, 2-5 words",
    }
]

GRAMMAR_SCHEMA = [
    {
        "topic": "one real grammar structure",
        "points": ["short grammar subpoint, 1-5 words"],
    }
]


def build_brief_prompt(user_request: str, previous_error: Optional[str] = None) -> str:
    payload = {
        "user_request": user_request,
        "task": (
            "Create a detailed lesson brief. "
            "This is a one-on-one English as a Second Language lesson with a tutor."
        ),
        "role": (
            "You are an ESL methodologist. Think carefully about the lesson request, "
            "student level, lesson goal, relevant vocabulary, relevant grammar, and useful practical skills."
        ),
        "rules": [
            "Return only valid JSON.",
            "Do not add markdown.",
            "Do not add explanations outside JSON.",
            "Do not shorten the brief.",
            "topic must contain 2-4 words.",

            "brief.lesson_goal must be detailed and specific.",
            "brief.lesson_goal must explain what the student should be able to do by the end of the lesson.",

            "brief.vocabulary must contain only vocabulary that is truly relevant to the request.",
            "If the request is clearly grammar-only, brief.vocabulary must be an empty array.",
            "If the user provides grammar and does not ask for vocabulary, do not invent vocabulary.",

            "brief.grammar must contain only grammar explicitly requested by the user.",
            "If the user request does not explicitly ask for grammar, brief.grammar must be an empty array.",
            "If grammar is requested, brief.grammar must contain exactly 1 grammar topic by default.",
            "Generate more than 1 grammar topic only if the user explicitly asks for several grammar topics.",
            "Each grammar item must be an object with topic and points.",
            "grammar.topic must be one real grammar structure.",
            "grammar.points must contain 1-4 short subpoints that explain what to cover inside this grammar topic.",
            "Do not put grammar subpoints as separate grammar topics.",
            "Example: use topic='Present Continuous' with points=['word markers', 'form'], not separate grammar items.",
            "Do not add grammar just because it is useful for the topic.",

            "Do not add irrelevant content.",

            "brief.practical_skills must contain only skills that are useful for this lesson.",
            "Use only 1-3 practical skills.",
            "brief.practical_skills must be an array of objects: {type, title}.",
            "practical_skills.type may include only: reading, listening, writing, speaking, pronunciation.",
            "Each practical_skills.title must be created by you and must be short, ideally 2-5 words.",
        ],
        "response_schema": {
            "status": "ok",
            "topic": "string, 2-4 words",
            "brief": {
                "lesson_goal": "detailed string",
                "vocabulary": ["string"],
                "grammar": GRAMMAR_SCHEMA,
                "practical_skills": PRACTICAL_SKILL_SCHEMA,
            },
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = (
            "Regenerate the whole JSON response and fix the validation error. "
            "Do not explain the fix."
        )

    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_improve_brief_prompt(
    request_data: ImproveBriefRequest,
    previous_error: Optional[str] = None,
) -> str:
    payload = {
        "topic": request_data.topic,
        "brief": request_data.brief.model_dump(),
        "improvement_request": request_data.improvement_request,
        "task": (
            "Improve the lesson brief according to improvement_request. "
            "The request can be any user input."
        ),
        "role": (
            "You are an ESL methodologist. Preserve useful existing content, "
            "but carefully update the brief where the user request requires it."
        ),
        "change_scope": (
            "Detect which fields the user wants to change: "
            "topic, lesson_goal, vocabulary, grammar, practical_skills. "
            "Only modify those fields. Preserve all other fields exactly."
        ),
        "rules": [
            "Return only valid JSON.",
            "Do not add markdown.",
            "Do not add explanations outside JSON.",
            "Do not shorten the brief.",
            "topic must remain 2-4 words.",

            "Determine the intended change scope from improvement_request.",
            "Only modify fields that are clearly requested by improvement_request.",
            "Fields outside the intended change scope must be copied exactly from the input brief.",
            "Do not change unrelated fields.",

            "If improvement_request asks to improve only grammar, preserve topic, vocabulary, and practical_skills exactly unchanged.",
            "If improvement_request asks to improve only vocabulary, preserve topic, grammar, and practical_skills exactly unchanged.",
            "If improvement_request asks to improve only practical skills, preserve topic, vocabulary, and grammar exactly unchanged.",
            "Do not remove, shorten, replace, or reorder existing vocabulary unless improvement_request explicitly asks to change vocabulary.",
            "Do not remove, shorten, replace, or reorder existing grammar unless improvement_request explicitly asks to change grammar.",

            "Keep vocabulary, grammar, practical_skills, and lesson_goal consistent with each other.",
            "brief.lesson_goal must be specific. Write in 1 sentence.",

            "brief.vocabulary must contain only vocabulary that is truly relevant to the request.",

            "brief.grammar must contain only grammar explicitly requested by the user.",
            "If grammar is not explicitly requested and the existing brief has no grammar, brief.grammar must be an empty array.",
            "If grammar is requested, brief.grammar must contain exactly 1 grammar topic by default.",
            "Generate more than 1 grammar topic only if the user explicitly asks for several grammar topics.",
            "Each grammar item must be an object with topic and points.",
            "grammar.topic must be one real grammar structure.",
            "grammar.points must contain 1-4 short subpoints that explain what to cover inside this grammar topic.",
            "Do not put grammar subpoints as separate grammar topics.",
            "Example: use topic='Present Continuous' with points=['word markers', 'form'], not separate grammar items.",

            "brief.practical_skills must contain only skills that are useful for this lesson.",
            "Use only 1-3 practical skills.",
            "brief.practical_skills must be an array of objects: {type, title}.",
            "practical_skills.type may include only: reading, listening, writing, speaking, pronunciation.",
            "Each practical_skills.title must be created or preserved by you and must be short, ideally 2-5 words.",
        ],
        "response_schema": {
            "status": "ok",
            "topic": "string, 2-4 words",
            "brief": {
                "lesson_goal": "detailed string",
                "vocabulary": ["string"],
                "grammar": GRAMMAR_SCHEMA,
                "practical_skills": PRACTICAL_SKILL_SCHEMA,
            },
        },
    }

    if previous_error:
        payload["previous_error"] = previous_error
        payload["fix_instruction"] = (
            "Regenerate the whole JSON response and fix the validation error. "
            "Do not explain the fix."
        )

    return json.dumps(payload, ensure_ascii=False, indent=2)


def detect_improvement_scope(improvement_request: str) -> set[str]:
    """
    Detects which brief fields the user explicitly wants to change.

    This is a conservative backend guard. It protects unrelated fields
    when the model tries to rewrite more than the user requested.
    """
    text = improvement_request.lower()
    scope = set()

    topic_markers = [
        "topic",
        "title",
        "тема",
        "название",
    ]
    goal_markers = [
        "goal",
        "aim",
        "цель",
        "результат",
    ]
    vocabulary_markers = [
        "vocabulary",
        "words",
        "lexis",
        "лексика",
        "слова",
        "словарь",
    ]
    grammar_markers = [
        "grammar",
        "грамматика",
        "грамматик",
    ]
    practical_skill_markers = [
        "skill",
        "skills",
        "навык",
        "навыки",
        "reading",
        "listening",
        "writing",
        "speaking",
        "pronunciation",
        "чтение",
        "аудирование",
        "письмо",
        "говорение",
        "произношение",
    ]

    if any(marker in text for marker in topic_markers):
        scope.add("topic")

    if any(marker in text for marker in goal_markers):
        scope.add("lesson_goal")

    if any(marker in text for marker in vocabulary_markers):
        scope.add("vocabulary")

    if any(marker in text for marker in grammar_markers):
        scope.add("grammar")

    if any(marker in text for marker in practical_skill_markers):
        scope.add("practical_skills")

    if not scope:
        scope = {
            "topic",
            "lesson_goal",
            "vocabulary",
            "grammar",
            "practical_skills",
        }

    return scope


def protect_unchanged_brief_fields(
    payload: dict[str, Any],
    request_data: ImproveBriefRequest,
) -> dict[str, Any]:
    """
    Restores unchanged fields after model generation.

    The model may rewrite fields even when the prompt tells it not to.
    This function makes field protection deterministic on the backend.
    """
    scope = detect_improvement_scope(request_data.improvement_request)

    if "topic" not in scope:
        payload["topic"] = request_data.topic

    if "brief" not in payload or not isinstance(payload["brief"], dict):
        return payload

    brief = payload["brief"]

    if "lesson_goal" not in scope:
        brief["lesson_goal"] = request_data.brief.lesson_goal

    if "vocabulary" not in scope:
        brief["vocabulary"] = request_data.brief.vocabulary

    if "grammar" not in scope:
        brief["grammar"] = [
            item.model_dump() for item in request_data.brief.grammar
        ]

    if "practical_skills" not in scope:
        brief["practical_skills"] = [
            item.model_dump() for item in request_data.brief.practical_skills
        ]

    return payload


def validate_brief_response(
    data: dict[str, Any],
    response_type: Type[GenerateBriefSuccessResponse] = GenerateBriefSuccessResponse,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    try:
        parsed = response_type.model_validate(data)
    except ValidationError as error:
        return False, str(error), None

    semantic_error = validate_brief_semantics(parsed.model_dump())
    if semantic_error:
        return False, semantic_error, None

    return True, None, parsed.model_dump()


def validate_brief_semantics(data: dict[str, Any]) -> Optional[str]:
    """
    Validates only structural and product constraints.
    Does NOT try to interpret or correct lesson meaning.
    """
    topic = data.get("topic")
    brief = data.get("brief")

    if not isinstance(topic, str) or not topic.strip():
        return "topic must be a non-empty string."

    topic_words = topic.strip().split()
    if not 2 <= len(topic_words) <= 4:
        return "topic must contain 2-4 words."

    if not isinstance(brief, dict):
        return "brief must be an object."

    lesson_goal = brief.get("lesson_goal")
    vocabulary = brief.get("vocabulary")
    grammar = brief.get("grammar")
    practical_skills = brief.get("practical_skills")

    if not isinstance(lesson_goal, str) or not lesson_goal.strip():
        return "brief.lesson_goal must be a non-empty string."

    if not isinstance(vocabulary, list):
        return "brief.vocabulary must be an array."

    if not isinstance(grammar, list):
        return "brief.grammar must be an array."

    if not isinstance(practical_skills, list):
        return "brief.practical_skills must be an array."

    if len(grammar) > 1:
        return "brief.grammar must contain only 1 grammar topic by default."

    if len(practical_skills) < 1:
        return "brief.practical_skills must contain at least 1 item."

    if len(practical_skills) > 3:
        return "brief.practical_skills must contain only 1-3 items."

    for item in vocabulary:
        if not isinstance(item, str) or not item.strip():
            return "Every vocabulary item must be a non-empty string."

    for grammar_item in grammar:
        if not isinstance(grammar_item, dict):
            return "Every grammar item must be an object."

        grammar_topic = grammar_item.get("topic")
        grammar_points = grammar_item.get("points")

        if not isinstance(grammar_topic, str) or not grammar_topic.strip():
            return "Every grammar.topic must be a non-empty string."

        if not isinstance(grammar_points, list):
            return "Every grammar.points must be an array."

        if len(grammar_points) < 1:
            return "Every grammar.points must contain at least 1 item."

        if len(grammar_points) > 4:
            return "Every grammar.points must contain only 1-4 items."

        for point in grammar_points:
            if not isinstance(point, str) or not point.strip():
                return "Every grammar.points item must be a non-empty string."

    for skill in practical_skills:
        if not isinstance(skill, dict):
            return "Every practical_skills item must be an object."

        skill_type = skill.get("type")
        title = skill.get("title")

        if skill_type not in PRACTICAL_SKILL_TYPES:
            return (
                "practical_skills.type must be one of: "
                "reading, listening, writing, speaking, pronunciation."
            )

        if not isinstance(title, str) or not title.strip():
            return "Every practical_skills.title must be a non-empty string."

    return None


async def generate_brief(request_data: GenerateBriefRequest) -> dict[str, Any]:
    settings = get_settings()
    user_request = trim_to_words_limit(request_data.user_request, max_words=1200)
    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        result = await generate(
            prompt=build_brief_prompt(user_request, previous_error=previous_error),
            temperature=0,
        )

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        is_valid, error_message, payload = validate_brief_response(result["data"])

        if is_valid and payload:
            return payload

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not generate valid lesson brief",
    }


async def improve_brief(request_data: ImproveBriefRequest) -> dict[str, Any]:
    settings = get_settings()

    improvement_request = trim_to_words_limit(
        request_data.improvement_request,
        max_words=500,
    )

    normalized_request = request_data.model_copy(
        update={"improvement_request": improvement_request},
    )

    previous_error = None

    for _ in range(settings.MAX_GENERATION_ATTEMPTS):
        result = await generate(
            prompt=build_improve_brief_prompt(
                normalized_request,
                previous_error=previous_error,
            ),
            temperature=0,
        )

        if result["status"] == "error":
            previous_error = result["message"]
            continue

        protected_data = protect_unchanged_brief_fields(
            result["data"],
            normalized_request,
        )

        is_valid, error_message, payload = validate_brief_response(
            protected_data,
            response_type=ImproveBriefSuccessResponse,
        )

        if is_valid and payload:
            return payload

        previous_error = error_message

    return {
        "status": "error",
        "message": previous_error or "Could not improve lesson brief",
    }