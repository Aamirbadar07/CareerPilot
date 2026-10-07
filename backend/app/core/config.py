from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "google"] = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    google_api_key: str = ""  # a Gemini API key from Google AI Studio
    # One model, or several separated by commas. Gemini counts its free-tier quota per
    # model, so the next one still has its own when the one before runs out.
    google_model: str = "gemini-3.8-flash"
    database_url: str = ""
    rapidapi_key: str = ""  # JSearch; the source is skipped when empty
    greenhouse_boards: str = "gitlab"  # comma-separated board tokens
    frontend_origin: str = "http://localhost:3000"  # the only origin CORS allows
    # How many proxies sit in front of the app, each appending one X-Forwarded-For entry.
    # 1 for Cloud Run or Render as they come; 2 behind an extra load balancer or CDN. Only
    # these last entries are trusted, so the per-IP rate limit cannot be reset with a header
    # (app/core/rate_limit.py). 0 keys the limit on the socket address alone.
    trusted_proxy_hops: int = 1
    # Uploaded profiles are deleted after this many hours (docs/decisions/0004-demo-mode.md).
    profile_ttl_hours: int = 24

    @property
    def google_models(self) -> list[str]:
        return [m.strip() for m in self.google_model.split(",") if m.strip()]

    @property
    def db_url(self) -> str:
        """SQLAlchemy URL. Supabase hands out postgres:// or postgresql://; we use psycopg 3."""
        url = self.database_url or "sqlite:///./careerpilot.db"
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url


settings = Settings()
