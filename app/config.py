from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str
    secret_key: str = Field(min_length=16)
    log_level: str = "INFO"
    log_file: str | None = None
    session_max_age: int = 8 * 60 * 60
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)


settings = Settings()
