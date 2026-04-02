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
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    youtube_redirect_uri: str = "http://127.0.0.1:8000/youtube/auth/callback"
    youtube_auth_scope: str = "https://www.googleapis.com/auth/youtube.force-ssl"
    youtube_token_path: str = "artifacts/reports/youtube_oauth_token.json"
    youtube_oauth_state_path: str = "artifacts/reports/youtube_oauth_state.json"
    youtube_language: str = "en-US"


settings = Settings()
