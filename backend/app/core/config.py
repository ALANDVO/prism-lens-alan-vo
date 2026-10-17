"""Application settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    app_name: str = "Prism Lens"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # --- Database ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./prism_lens.db",
        alias="DATABASE_URL",
    )

    # --- Auth (Keycloak OIDC) ---
    keycloak_server_url: str = Field(
        default="http://keycloak:8080", alias="KEYCLOAK_SERVER_URL"
    )
    keycloak_realm: str = Field(default="prism-lens", alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(default="prism-lens", alias="KEYCLOAK_CLIENT_ID")
    oidc_redirect_uri: str = Field(
        default="http://localhost:5173/callback", alias="OIDC_REDIRECT_URI"
    )
    dev_mode: bool = Field(default=False, alias="DEV_MODE")

    # --- LLM ---
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_provider: str | None = Field(default=None, alias="LLM_PROVIDER")
    llm_model: str | None = Field(
        default="gpt-4o-mini", alias="LLM_MODEL"
    )
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_timeout_seconds: int = Field(default=30, alias="LLM_TIMEOUT_SECONDS")

    # --- Upload ---
    upload_max_bytes: int = Field(default=50_000_000, alias="UPLOAD_MAX_BYTES")

    # --- Derived ---
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()


def get_settings() -> Settings:
    """Dependency that returns the singleton settings."""
    return settings