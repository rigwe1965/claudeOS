import logging
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator

_log = logging.getLogger("claudeos.config")


BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    # Core
    CLAUDEOS_SECRET_KEY: str  # Required — no default; must be set in .env
    CLAUDEOS_ENV: str = "development"
    CLAUDEOS_VERSION: str = "1.0.0"

    # Claude API
    ANTHROPIC_API_KEY: str = ""
    # Model overrides — blank = latest (see core/models.py)
    CLAUDE_MODEL: str = ""
    CLAUDE_FAST_MODEL: str = ""

    # Web Intelligence — all optional, system works without any keys (falls back to DuckDuckGo)
    # Brave Search: 2000 free/month — https://api.search.brave.com (best free-tier quality)
    BRAVE_SEARCH_KEY: str = ""
    # Tavily: 1000 free/month — https://tavily.com (built for AI agents)
    TAVILY_API_KEY: str = ""
    # NewsAPI: 100 free/day — https://newsapi.org (structured news with full dates)
    NEWSAPI_KEY: str = ""

    # Database
    SQLITE_PATH: str = "data/claudeos.db"
    CHROMADB_PATH: str = "data/chromadb"

    # Flask
    FLASK_PORT: int = 5000
    FLASK_DEBUG: bool = False

    # Streamlit
    STREAMLIT_PORT: int = 8501

    # Supabase (Phase 7)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_ACCESS_TOKEN: str = ""  # Personal access token for Management API

    # Scheduler
    SCHEDULER_TIMEZONE: str = "Europe/Berlin"  # Set in .env to override (e.g. UTC, Africa/Lagos, America/New_York)

    # Memory bridge
    CLAUDE_MEMORY_PATH: str = ""  # Set in .env to enable /memory/import

    # RECI Transport
    RECI_DASHBOARD_DB: str = ""

    # Email notifications
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    NOTIFY_EMAIL: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_PATH: str = "logs"

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def warn_missing_keys(self) -> "Settings":
        if not self.ANTHROPIC_API_KEY:
            _log.warning("ANTHROPIC_API_KEY is not set — all agent runs will fail with 401")
        if not self.CLAUDE_MEMORY_PATH:
            _log.debug("CLAUDE_MEMORY_PATH not set — /memory/import endpoint disabled")
        return self

    @field_validator("CLAUDEOS_SECRET_KEY")
    @classmethod
    def secret_not_default(cls, v: str) -> str:
        _BAD = {"dev-secret-change-in-prod", "change-me-random-32-chars", ""}
        if not v or v in _BAD:
            raise ValueError(
                "CLAUDEOS_SECRET_KEY must be set to a random secret in .env "
                "(not the example value)"
            )
        if len(v) < 32:
            raise ValueError("CLAUDEOS_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("SQLITE_PATH", "CHROMADB_PATH", "LOG_PATH", mode="before")
    @classmethod
    def resolve_path(cls, v: str) -> str:
        p = Path(v)
        if not p.is_absolute():
            return str(BASE_DIR / v)
        return v

    def __repr__(self) -> str:
        _MASKED = {"CLAUDEOS_SECRET_KEY", "ANTHROPIC_API_KEY", "SMTP_PASSWORD",
                   "SUPABASE_SERVICE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_ACCESS_TOKEN"}
        parts = []
        for k, v in self.__dict__.items():
            parts.append(f"{k}={'***' if k in _MASKED and v else repr(v)}")
        return f"Settings({', '.join(parts)})"

    @property
    def is_production(self) -> bool:
        return self.CLAUDEOS_ENV == "production"

    @property
    def sqlite_path(self) -> Path:
        return Path(self.SQLITE_PATH)

    @property
    def chromadb_path(self) -> Path:
        return Path(self.CHROMADB_PATH)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        # Ensure data dirs exist
        _settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        _settings.chromadb_path.mkdir(parents=True, exist_ok=True)
        Path(_settings.LOG_PATH).mkdir(parents=True, exist_ok=True)
    return _settings
