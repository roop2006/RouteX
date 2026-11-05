from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    tomtom_api_key: str | None = None
    tomtom_cache_ttl_seconds: int = 300
    tomtom_traffic_base_url: str = "https://api.tomtom.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
