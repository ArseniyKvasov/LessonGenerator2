import json
from typing import Any, Literal

from groq import Groq

from app.config import LIGHT_MODELS, PRO_MODELS, get_settings


ModelType = Literal["light", "pro"]


def get_model_by_type(model_type: ModelType) -> str:
    settings = get_settings()

    if model_type == "light":
        if settings.LIGHT_MODEL not in LIGHT_MODELS:
            return LIGHT_MODELS[0]

        return settings.LIGHT_MODEL

    if settings.PRO_MODEL not in PRO_MODELS:
        return PRO_MODELS[0]

    return settings.PRO_MODEL


def generate(prompt: str, model_type: ModelType = "light") -> dict[str, Any]:
    """
    Sends prompt to Groq and returns a unified JSON response.

    Returns:
        {
            "status": "ok",
            "data": {...}
        }

        or

        {
            "status": "error",
            "message": "..."
        }
    """
    settings = get_settings()
    model = get_model_by_type(model_type)

    client = Groq(api_key=settings.GROQ_API_KEY)

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a JSON API. "
                        "Return only valid JSON. "
                        "Do not use markdown. "
                        "Do not add explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={
                "type": "json_object",
            },
        )

        content = response.choices[0].message.content

        if not content:
            return {
                "status": "error",
                "message": "Empty response from Groq",
            }

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "message": "Groq returned invalid JSON",
            }

        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Groq response JSON must be an object",
            }

        return {
            "status": "ok",
            "data": data,
        }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }