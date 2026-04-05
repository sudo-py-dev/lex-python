from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    DATABASE_URL: str
    REDIS_URL: str
    OWNER_ID: int
    LOG_LEVEL: str = "INFO"
    RATE_LIMIT_DELAY: float = 2.0
    BOT_NAME: str = "lex-tg"
    VERSION: str = "0.0.1"


config = Config()

TECH_STACK = {
    "engine": "[Kurigram](https://github.com/KurimuzonAkuma/kurigram) (Pyrogram Fork)",
    "database": "PostgreSQL (Async) & Redis",
    "framework": "SQLAlchemy 2.0 & Alembic",
    "performance": "Uvloop & Loguru",
}
