"""Environment-based configuration for SalesLeads platform."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    return int(os.getenv(key, str(default)))


@dataclass(frozen=True)
class Settings:
    # LLM
    ollama_base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "llama3"))

    # API Keys
    apollo_api_key: str = field(default_factory=lambda: _env("APOLLO_API_KEY"))
    hunter_api_key: str = field(default_factory=lambda: _env("HUNTER_API_KEY"))
    clearbit_api_key: str = field(default_factory=lambda: _env("CLEARBIT_API_KEY"))
    nyc_opendata_app_token: str = field(default_factory=lambda: _env("NYC_OPENDATA_APP_TOKEN"))

    # Database
    database_path: str = field(default_factory=lambda: _env("DATABASE_PATH", "salesleads.db"))

    # Scheduling
    daily_run_hour: int = field(default_factory=lambda: _env_int("DAILY_RUN_HOUR", 6))
    marketplace_interval_hours: int = field(default_factory=lambda: _env_int("MARKETPLACE_INTERVAL_HOURS", 4))

    # Agent Settings
    max_agent_workers: int = field(default_factory=lambda: _env_int("MAX_AGENT_WORKERS", 4))
    agent_timeout_seconds: int = field(default_factory=lambda: _env_int("AGENT_TIMEOUT_SECONDS", 300))

    # LinkedIn
    linkedin_email: str = field(default_factory=lambda: _env("LINKEDIN_EMAIL"))
    linkedin_password: str = field(default_factory=lambda: _env("LINKEDIN_PASSWORD"))

    # Dedup
    dedup_similarity_threshold: int = field(default_factory=lambda: _env_int("DEDUP_SIMILARITY_THRESHOLD", 85))

    # Dashboard
    streamlit_port: int = field(default_factory=lambda: _env_int("STREAMLIT_PORT", 8501))

    # FastAPI
    fastapi_port: int = field(default_factory=lambda: _env_int("FASTAPI_PORT", 8000))
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "http://localhost:5173"))

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)
