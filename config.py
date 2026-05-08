"""
OmniLens v3.0 - Centralized Configuration
Uses Pydantic Settings for type-safe environment variable loading.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- Application ---
    app_name: str = Field(default="OmniLens", alias="APP_NAME")
    app_version: str = Field(default="3.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Database ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./omnilens.db",
        alias="DATABASE_URL"
    )

    # --- Google Drive ---
    google_client_secrets_file: str = Field(
        default="client_secrets.json",
        alias="GOOGLE_CLIENT_SECRETS_FILE"
    )
    google_token_file: str = Field(
        default="token.json",
        alias="GOOGLE_TOKEN_FILE"
    )
    google_scopes: str = Field(
        default="https://www.googleapis.com/auth/drive.readonly",
        alias="GOOGLE_SCOPES"
    )

    # --- S3-Compatible Storage ---
    s3_endpoint_url: Optional[str] = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_access_key: Optional[str] = Field(default=None, alias="S3_ACCESS_KEY")
    s3_secret_key: Optional[str] = Field(default=None, alias="S3_SECRET_KEY")
    s3_bucket_name: Optional[str] = Field(default=None, alias="S3_BUCKET_NAME")
    s3_region: str = Field(default="auto", alias="S3_REGION")

    # --- Backblaze B2 (optional separate config) ---
    b2_endpoint_url: Optional[str] = Field(default=None, alias="B2_ENDPOINT_URL")
    b2_application_key_id: Optional[str] = Field(default=None, alias="B2_APPLICATION_KEY_ID")
    b2_application_key: Optional[str] = Field(default=None, alias="B2_APPLICATION_KEY")
    b2_bucket_name: Optional[str] = Field(default=None, alias="B2_BUCKET_NAME")

    # --- Webhook Security ---
    google_webhook_token: Optional[str] = Field(default=None, alias="GOOGLE_WEBHOOK_TOKEN")
    s3_webhook_secret: Optional[str] = Field(default=None, alias="S3_WEBHOOK_SECRET")

    # --- Rate Limiting ---
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_burst: int = Field(default=10, alias="RATE_LIMIT_BURST")

    # --- CORS ---
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # --- Thumbnails ---
    thumbnail_max_width: int = Field(default=400, alias="THUMBNAIL_MAX_WIDTH")
    thumbnail_max_height: int = Field(default=400, alias="THUMBNAIL_MAX_HEIGHT")
    thumbnail_format: str = Field(default="webp", alias="THUMBNAIL_FORMAT")
    thumbnail_quality: int = Field(default=85, alias="THUMBNAIL_QUALITY")

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins into list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def google_scopes_list(self) -> List[str]:
        """Return Google scopes as a list."""
        return self.google_scopes.split()

    @property
    def is_s3_configured(self) -> bool:
        """Check if S3 credentials are fully configured."""
        return all([
            self.s3_endpoint_url,
            self.s3_access_key,
            self.s3_secret_key,
            self.s3_bucket_name
        ])

    @property
    def is_b2_configured(self) -> bool:
        """Check if Backblaze B2 credentials are fully configured."""
        return all([
            self.b2_endpoint_url,
            self.b2_application_key_id,
            self.b2_application_key,
            self.b2_bucket_name
        ])


# Global settings instance
settings = Settings()
