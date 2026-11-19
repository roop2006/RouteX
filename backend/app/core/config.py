from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    database_url: str
    tomtom_api_key: str | None = None
    tomtom_cache_ttl_seconds: int = 300
    tomtom_traffic_base_url: str = "https://api.tomtom.com"
    osrm_base_url: str = "https://router.project-osrm.org"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
