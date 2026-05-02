from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_MODEL_POOL = [
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "allam-2-7b",
    "openai/gpt-oss-20b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
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

    MODEL_POOL: str = ",".join(DEFAULT_MODEL_POOL)
    DEFAULT_MODEL_COOLDOWN_SECONDS: int = 60
    MAX_GENERATION_ATTEMPTS: int = 3
    GROQ_MAX_TOKENS: int = 4096
    AUDIO_GENERATION_TIMEOUT_SECONDS: int = 60
    IMAGE_GENERATION_TIMEOUT_SECONDS: int = 60

    def model_pool(self) -> list[str]:
        models = [model.strip() for model in self.MODEL_POOL.split(",") if model.strip()]
        return models or DEFAULT_MODEL_POOL


@lru_cache
def get_settings() -> Settings:
    return Settings()
