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
    SUPPORT_URL: str = "https://www.buymeacoffee.com/sudo-py-dev"
    GITHUB_SPONSORS_URL: str = "https://github.com/sponsors/sudo-py-dev"
    ENABLE_VIDEO_WATERMARK: bool = False
    VIDEO_WATERMARK_MAX_SIZE_MB: int = 50
    AI_GUARD_MODEL: str = "llama-3.1-8b-instant"
    AI_GUARD_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    AI_GUARD_MAX_IMAGE_SIZE_MB: int = 10


try:
    config = Config()
except Exception as e:
    print("\n" + "="*50)
    print("❌ CONFIGURATION ERROR")
    print("="*50)
    print("One or more required environment variables are missing.")
    print("Please check your Railway dashboard and ensure these are set:")
    print(" - API_ID")
    print(" - API_HASH")
    print(" - BOT_TOKEN")
    print(" - DATABASE_URL")
    print(" - OWNER_ID")
    print("\nMore details:")
    print(e)
    print("="*50 + "\n")
    import sys
    sys.exit(1)

TECH_STACK = {
    "engine": "[Kurigram](https://github.com/KurimuzonAkuma/kurigram) (Pyrogram Fork)",
    "database": "PostgreSQL (Async)",
    "cache": "Pure Python (Local Snapshot)",
    "framework": "SQLAlchemy 2.0 & Alembic",
    "performance": "Uvloop & Loguru",
}
