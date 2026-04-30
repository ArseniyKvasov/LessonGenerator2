from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


LIGHT_MODELS = [
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "llama-3.1-70b-versatile",
    "openai/gpt-oss-20b",
]

PRO_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-405b-reasoning",
    "deepseek-r1-distill-llama-70b",
    "openai/gpt-oss-120b",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    API_KEY: str
    GROQ_API_KEY: str
    POLLINATIONS_API_KEY: str

    LIGHT_MODEL: str = "llama-3.1-8b-instant"
    PRO_MODEL: str = "llama-3.3-70b-versatile"

    MAX_GENERATION_ATTEMPTS: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
