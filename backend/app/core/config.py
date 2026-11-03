from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://viewtube:viewtube@localhost:5432/viewtube"
    app_origin: str = "http://localhost:8080"
    cookie_secure: bool = False
    secret_key: str = Field(min_length=32)
    s3_endpoint: str = "http://storage:8333"
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "viewtube"
    s3_region: str = "us-east-1"
    max_upload_bytes: int = 536870912
    max_duration_seconds: int = 7200
    session_days: int = 14
    worker_timeout_seconds: int = 3600
    worker_max_attempts: int = 3
    # No exception for staff; only owners and explicit recipients may watch private videos.
    staff_private_access: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
