import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GEMINI_API_KEY: str = ""
    SQLITE_DB_PATH: str = "sqlite:///./cognitrace.db"
    CORS_ORIGINS: str = (
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_TYPES: str = "pdf,docx,txt,md,csv,json"
    UPLOAD_DIR: str = "uploads"
    REPORTS_DIR: str = "reports"


settings = Settings()

# Ensure upload and reports directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
