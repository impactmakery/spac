from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, loaded from the repo-root .env (single env file for the API)."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = ""
    jwt_secret: str = ""
    nextauth_url: str = ""
    api_base_url: str = ""
    # LLM access. Any OpenAI-compatible endpoint works (OpenAI, OpenRouter, …);
    # switching provider is an env change, never a code change. The *_api_key
    # and *_base_url settings fall back to the OpenAI ones when unset, so an
    # OpenAI-only deployment needs nothing but OPENAI_API_KEY.
    openai_api_key: str = ""
    openai_base_url: str = ""

    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4.1"
    # Tried in order when the primary is rate-limited or returns nothing —
    # free tiers run out, and a dead assistant is worse than a slower one.
    llm_fallback_models: str = ""

    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-3-large"

    # Sent by OpenRouter for attribution; harmless elsewhere.
    openrouter_site_url: str = ""
    openrouter_app_name: str = "Tomorrow Agent Hub"

    # A key and its base URL are one credential pair: never authenticate against
    # one provider's endpoint with another provider's key. So each resolver picks
    # the URL belonging to whichever key it selected.

    @property
    def resolved_llm_key(self) -> str:
        return self.llm_api_key or self.openai_api_key

    @property
    def resolved_llm_base_url(self) -> str | None:
        if self.llm_api_key:
            return self.llm_base_url or None
        return self.openai_base_url or None

    @property
    def resolved_embedding_key(self) -> str:
        return self.embedding_api_key or self.llm_api_key or self.openai_api_key

    @property
    def resolved_embedding_base_url(self) -> str | None:
        if self.embedding_api_key:
            return self.embedding_base_url or None
        if self.llm_api_key:
            return self.embedding_base_url or self.llm_base_url or None
        return self.embedding_base_url or self.openai_base_url or None

    @property
    def llm_model_chain(self) -> list[str]:
        extra = [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]
        return [self.llm_model, *extra]
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    # Buckets created with a jurisdiction ("eu", "fedramp") must be reached
    # through that jurisdiction's endpoint; plain buckets use the default host.
    r2_jurisdiction: str = ""

    @property
    def r2_endpoint_url(self) -> str:
        host = f"{self.r2_account_id}.r2.cloudflarestorage.com"
        if self.r2_jurisdiction:
            host = f"{self.r2_account_id}.{self.r2_jurisdiction}.r2.cloudflarestorage.com"
        return f"https://{host}"
    resend_api_key: str = ""
    email_from: str = ""
    cron_secret: str = ""
    outbox_dir: str = "var/outbox"

    # First system administrator, created on boot only when the platform has no
    # users at all. Lets a fresh deployment be opened without shell access;
    # ignored forever after, so leaving them set is harmless.
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    files_dir: str = "var/files"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Hosting platforms hand out bare postgres:// or postgresql:// URLs, which
    # SQLAlchemy maps to psycopg2 — a driver we deliberately do not install.
    # Normalise to psycopg 3 so the platform's URL works unedited.
    url = settings.database_url
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            settings.database_url = "postgresql+psycopg://" + url[len(prefix) :]
            break
    return settings
