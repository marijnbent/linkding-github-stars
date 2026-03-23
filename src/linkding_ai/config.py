from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    linkding_base_url: str = Field(..., alias="LINKDING_BASE_URL")
    linkding_token: str = Field(..., alias="LINKDING_TOKEN")
    github_token: str | None = Field(None, alias="GITHUB_TOKEN")
    openrouter_api_key: str | None = Field(None, alias="OPENROUTER_API_KEY")
    openrouter_model: str | None = Field(None, alias="OPENROUTER_MODEL")
    openrouter_base_url: str = Field(
        "https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    github_api_base_url: str = Field(
        "https://api.github.com",
        alias="GITHUB_API_BASE_URL",
    )
    request_timeout: float = Field(30.0, alias="REQUEST_TIMEOUT")
    sync_interval: int = Field(3600, alias="SYNC_INTERVAL")
    ai_processed_tag: str = Field("ai-tagged", alias="AI_PROCESSED_TAG")
    max_ai_tags: int = Field(8, alias="MAX_AI_TAGS")
    ai_summary_label: str = Field("AI Summary", alias="AI_SUMMARY_LABEL")
    user_agent: str = Field("linkding-ai-sync/0.1.0", alias="USER_AGENT")
    openrouter_app_name: str = Field(
        "Linkding AI Sync",
        alias="OPENROUTER_APP_NAME",
    )
    openrouter_site_url: str | None = Field(None, alias="OPENROUTER_SITE_URL")

    @field_validator("linkding_base_url", "openrouter_base_url", "github_api_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("sync_interval")
    @classmethod
    def validate_sync_interval(cls, value: int) -> int:
        if value < 60:
            raise ValueError("SYNC_INTERVAL must be at least 60 seconds")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
