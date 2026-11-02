from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "google", "openrouter", "deepseek"] = "google"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    google_api_key: str = ""  # a Gemini API key from Google AI Studio (or comma-separated keys)
    # One model, or several separated by commas. Gemini counts its free-tier quota per
    # model, so the next one still has its own when the one before runs out.
    google_model: str = "gemma-4-26b-a4b-it,gemini-3.8-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-chat"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    database_url: str = ""
    rapidapi_key: str = ""  # JSearch; the source is skipped when empty
    greenhouse_boards: str = "gitlab"  # comma-separated board tokens
    frontend_origin: str = "http://localhost:3000"  # the origin(s) CORS allows; comma-separated
    # How many proxies sit in front of the app, each appending one X-Forwarded-For entry.
    # 1 for Cloud Run or Render as they come; 2 behind an extra load balancer or CDN. Only
    # these last entries are trusted, so the per-IP rate limit cannot be reset with a header
    # (app/core/rate_limit.py). 0 keys the limit on the socket address alone.
    trusted_proxy_hops: int = 1
    # Uploaded profiles are deleted after this many hours (docs/decisions/0004-demo-mode.md).
    profile_ttl_hours: int = 24
    # Deterministic topological priority routing skips unnecessary LLM router calls
    deterministic_routing: bool = True

    @property
    def frontend_origins(self) -> list[str]:
        """FRONTEND_ORIGIN as a list of allowed origins, supporting multiple comma-separated URLs."""
        origins = [o.strip() for o in self.frontend_origin.split(",") if o.strip()]
        return origins or ["http://localhost:3000"]

    @property
    def google_api_keys(self) -> list[str]:
        """GOOGLE_API_KEY as a list, supporting comma-separated or newline-separated multiple keys
        for key rotation across multiple Google accounts or projects."""
        if not self.google_api_key:
            return []
        keys = [
            k.strip()
            for part in self.google_api_key.replace("\n", ",").split(",")
            if (k := part.strip())
        ]
        return keys

    @property
    def anthropic_api_keys(self) -> list[str]:
        """ANTHROPIC_API_KEY as a list, supporting comma-separated multiple keys."""
        if not self.anthropic_api_key:
            return []
        keys = [
            k.strip()
            for part in self.anthropic_api_key.replace("\n", ",").split(",")
            if (k := part.strip())
        ]
        return keys

    @property
    def google_models(self) -> list[str]:
        """GOOGLE_MODEL as a list. An empty or blank value falls back to the default rather
        than to no model at all: a variable left empty in a hosting dashboard is the normal
        way this happens."""
        names = [m.strip() for m in self.google_model.split(",") if m.strip()]
        return names or [type(self).model_fields["google_model"].default]

    @property
    def db_url(self) -> str:
        """SQLAlchemy URL. Supabase hands out postgres:// or postgresql://; we use psycopg 3."""
        url = self.database_url or "sqlite:///./careerpilot.db"
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url


settings = Settings()
