"""
config.py
=========
Loads environment variables from .env using python-dotenv.
All database and server configuration is centralised here.
"""

import os
from dotenv import load_dotenv

# Load .env file from the backend/ directory
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)


class Settings:
    """Application settings derived from environment variables."""

    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "ai_project_intelligence")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "your_password")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    @property
    def DATABASE_URL(self) -> str:
        """SQLAlchemy-compatible PostgreSQL connection string."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
