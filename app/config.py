"""
Configuration — loads environment variables from .env.
All settings are consumed from this single module.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv(override=True)  # override=True forces re-read even if vars already set


class Settings:
    """Application-wide settings resolved from environment variables."""

    # -------------------------------------------------------------------------
    # Groq API (OpenAI-compatible)
    # -------------------------------------------------------------------------
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_API_URL: str = os.getenv(
        "GROQ_API_URL",
        "https://api.groq.com/openai/v1/chat/completions",
    )
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # -------------------------------------------------------------------------
    # File Upload Constraints
    # -------------------------------------------------------------------------
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

    # -------------------------------------------------------------------------
    # Scoring Thresholds
    # -------------------------------------------------------------------------
    JOB_READY_THRESHOLD: int = int(os.getenv("JOB_READY_THRESHOLD", "40"))

    # -------------------------------------------------------------------------
    # Request / Response
    # -------------------------------------------------------------------------
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    def validate(self) -> None:
        if not self.GROQ_API_KEY:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file. Get a free key at https://console.groq.com/"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    settings = Settings()
    settings.validate()
    return settings


settings = get_settings()
