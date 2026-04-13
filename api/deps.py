"""Shared FastAPI dependencies."""

from functools import lru_cache

from config.settings import Settings
from core.database import Database


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.database_path)
