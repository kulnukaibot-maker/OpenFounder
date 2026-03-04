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
    CEO_MODEL: str = os.getenv("CEO_MODEL", "claude-sonnet-4-6-20250514")
    CREW_MODEL: str = os.getenv("CREW_MODEL", "claude-sonnet-4-6-20250514")

    # CEO Loop
    CEO_MAX_TOKENS: int = int(os.getenv("CEO_MAX_TOKENS", "4096"))
    CEO_TEMPERATURE: float = float(os.getenv("CEO_TEMPERATURE", "0.3"))

    # Discord
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
