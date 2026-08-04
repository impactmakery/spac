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
    openai_api_key: str = ""
    llm_model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-large"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    resend_api_key: str = ""
    email_from: str = ""
    cron_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
