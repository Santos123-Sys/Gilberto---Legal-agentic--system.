from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    MARITACA_API_KEY: str = ""
    MARITACA_BASE_URL: str = "https://chat.maritaca.ai/api"
    MARITACA_MODEL: str = "sabia-4"
    MAX_AGENTS: int = 5
    MAX_ROUNDS: int = 5
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7
    CORS_ORIGINS: str = "*"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
