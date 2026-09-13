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
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    scan_interval_seconds: int = max(10, int(os.getenv("SCAN_INTERVAL_SECONDS", "30")))
    trend_interval_seconds: int = max(5, int(os.getenv("TREND_INTERVAL_SECONDS", "10")))
    source_timeout_seconds: int = max(3, int(os.getenv("SOURCE_TIMEOUT_SECONDS", "8")))
    max_articles_per_source: int = max(10, int(os.getenv("MAX_ARTICLES_PER_SOURCE", "100")))
    publish_mode: str = os.getenv("PUBLISH_MODE", "manual")
    auto_publish_score: float = float(os.getenv("AUTO_PUBLISH_SCORE", "92"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
settings = Settings()
