from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    DATABASE_URL: str
    OWNER_ID: int
    LOG_LEVEL: str = "INFO"
    BOT_NAME: str = "lex-tg"
    GITHUB_URL: str = "https://github.com/sudo-py-dev/lex-tg"
    DEV_NAME: str = "sudo-py-dev"
    DEV_URL: str = "https://github.com/sudo-py-dev"
    VERSION: str = "0.0.1"
    ENABLE_VIDEO_WATERMARK: bool
    VIDEO_WATERMARK_MAX_SIZE_MB: int
    AI_GUARD_MODEL: str = "llama-3.1-8b-instant"


config = Config()

TECH_STACK = {
    "engine": "[Kurigram](https://github.com/KurimuzonAkuma/kurigram) (Pyrogram Fork)",
    "database": "PostgreSQL (Async)",
    "cache": "Pure Python (Local Snapshot)",
    "framework": "SQLAlchemy 2.0 & Alembic",
    "performance": "Uvloop & Loguru",
}
