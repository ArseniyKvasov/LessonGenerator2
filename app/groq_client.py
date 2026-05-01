import json
import re
import time
from typing import Any, Optional

from groq import AsyncGroq

from app.config import get_settings


_unavailable_until: dict[str, float] = {}


def _now() -> float:
    return time.time()


def extract_retry_after_seconds(message: str) -> Optional[float]:
    """Extract Groq retry hints like '34m3.36s' from rate-limit messages."""
    match = re.search(r"try again in\s+([0-9hms.\s]+)", message, flags=re.IGNORECASE)
    if not match:
        return None

    retry_hint = match.group(1).strip().rstrip(".")
    total_seconds = 0.0

    for value, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", retry_hint):
        amount = float(value)
        if unit == "ms":
            total_seconds += amount / 1000
        elif unit == "s":
            total_seconds += amount
        elif unit == "m":
            total_seconds += amount * 60
        elif unit == "h":
            total_seconds += amount * 3600

    return total_seconds or None


def _is_rate_limit_error(message: str) -> bool:
    normalized = message.casefold()
    return (
        "rate limit" in normalized
        or "rate_limit" in normalized
        or "too many requests" in normalized
        or "try again in" in normalized
    )


def mark_model_unavailable(model: str, message: str) -> None:
    settings = get_settings()
    retry_after = extract_retry_after_seconds(message)
    cooldown = retry_after if retry_after is not None else settings.DEFAULT_MODEL_COOLDOWN_SECONDS
    _unavailable_until[model] = _now() + max(cooldown, 1)


def available_models() -> list[str]:
    now = _now()
    try:
        settings = get_settings()
    except Exception:
        return []

    return [
        model
        for model in settings.model_pool()
        if _unavailable_until.get(model, 0) <= now
    ]


def models_available() -> bool:
    return bool(available_models())


def availability_snapshot() -> dict[str, Any]:
    return {
        "models_available": models_available(),
    }


async def generate(
    prompt: str,
    *,
    temperature: float = 0,
    max_tokens: Optional[int] = None,
) -> dict[str, Any]:
    """
    Send a JSON-only prompt to Groq through one unified model pool.

    Models that hit a rate limit are marked unavailable until Groq's retry hint
    passes, or for DEFAULT_MODEL_COOLDOWN_SECONDS when no hint can be parsed.
    """
    try:
        settings = get_settings()
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    last_error: Optional[str] = None
    models = available_models()

    if not models:
        return {
            "status": "error",
            "message": "No Groq models are currently available",
        }

    for model in models:
        try:
            response = await client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a JSON API. Return only valid JSON. "
                            "Do not use markdown outside JSON strings. "
                            "Do not add explanations outside JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens or settings.GROQ_MAX_TOKENS,
            )

            content = response.choices[0].message.content
            if not content:
                return {
                    "status": "error",
                    "message": "Empty response from Groq",
                }

            try:
                data = json.loads(content)
            except json.JSONDecodeError as error:
                return {
                    "status": "error",
                    "message": f"Groq returned invalid JSON: {error}",
                }

            if not isinstance(data, dict):
                return {
                    "status": "error",
                    "message": "Groq response JSON must be an object",
                }

            return {
                "status": "ok",
                "data": data,
                "model": model,
            }

        except Exception as error:
            last_error = str(error)
            if _is_rate_limit_error(last_error):
                mark_model_unavailable(model, last_error)
                continue

            return {
                "status": "error",
                "message": last_error,
            }

    return {
        "status": "error",
        "message": last_error or "No Groq models are currently available",
    }
