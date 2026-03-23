from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRUTHLENS_", env_file=".env", extra="ignore")

    env: str = "local"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://truthlens:truthlens@localhost:5432/truthlens"
    redis_url: str = "redis://localhost:6379/0"
    model_version: str = "bootstrap-v0"
    policy_version: str = "bootstrap-v0"
    log_level: str = "INFO"
    feedback_log_path: str = "artifacts/reports/feedback_events.jsonl"
    require_api_key: bool = False
    api_key: str | None = None
    rate_limit_per_minute: int = 240


settings = Settings()
