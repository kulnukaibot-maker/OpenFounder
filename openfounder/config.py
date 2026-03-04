"""Environment-based configuration loader."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://openfounder:openfounder_dev@localhost:5433/openfounder",
    )

    # LLM
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CEO_MODEL: str = os.getenv("CEO_MODEL", "claude-haiku-4-5-20251001")
    CREW_MODEL: str = os.getenv("CREW_MODEL", "claude-haiku-4-5-20251001")
    ESCALATION_MODEL: str = os.getenv("ESCALATION_MODEL", "claude-sonnet-4-20250514")
    MAX_MODEL: str = os.getenv("MAX_MODEL", "claude-opus-4-20250514")

    # CEO Loop
    CEO_MAX_TOKENS: int = int(os.getenv("CEO_MAX_TOKENS", "4096"))
    CREW_MAX_TOKENS: int = int(os.getenv("CREW_MAX_TOKENS", "8192"))
    CEO_TEMPERATURE: float = float(os.getenv("CEO_TEMPERATURE", "0.3"))

    # Engineering crew — code execution
    ENGINEERING_MODEL: str = os.getenv("ENGINEERING_MODEL", "claude-sonnet-4-20250514")
    ENGINEERING_MAX_TOKENS: int = int(os.getenv("ENGINEERING_MAX_TOKENS", "16384"))
    ENGINEERING_AUTO_APPLY: bool = os.getenv("ENGINEERING_AUTO_APPLY", "false").lower() in ("true", "1", "yes")
    ENGINEERING_REPO_PATH: str = os.getenv("ENGINEERING_REPO_PATH", "")
    ENGINEERING_TEST_TIMEOUT: int = int(os.getenv("ENGINEERING_TEST_TIMEOUT", "120"))

    # Discord
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
