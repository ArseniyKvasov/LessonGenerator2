import json
import random
from typing import Any, Literal

from groq import AsyncGroq

from app.config import LIGHT_MODELS, PRO_MODELS, get_settings


ModelType = Literal["light", "pro"]


_LAST_MODEL_BY_TYPE: dict[ModelType, str] = {}


def get_model_by_type(model_type: ModelType) -> str:
    settings = get_settings()
    models_pool = LIGHT_MODELS if model_type == "light" else PRO_MODELS

    preferred_model = settings.LIGHT_MODEL if model_type == "light" else settings.PRO_MODEL

    if preferred_model in models_pool:
        # Keep preferred model in pool, but do not force it on each retry.
        available_models = models_pool
    else:
        available_models = models_pool

    if len(available_models) == 1:
        selected_model = available_models[0]
    else:
        last_model = _LAST_MODEL_BY_TYPE.get(model_type)
        candidates = [model for model in available_models if model != last_model]
        if not candidates:
            candidates = available_models
        selected_model = random.choice(candidates)

    _LAST_MODEL_BY_TYPE[model_type] = selected_model

    return selected_model


async def generate(prompt: str, model_type: ModelType = "light") -> dict[str, Any]:
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

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    try:
        response = await client.chat.completions.create(
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
            max_tokens=4096,
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
