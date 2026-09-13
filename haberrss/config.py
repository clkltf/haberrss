import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ["DATABASE_URL"]
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    scan_interval_seconds: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))
    trend_interval_seconds: int = int(os.getenv("TREND_INTERVAL_SECONDS", "30"))
    publish_mode: str = os.getenv("PUBLISH_MODE", "manual")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
