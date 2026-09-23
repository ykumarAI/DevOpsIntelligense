import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _default_data_dir() -> Path:
    """Per-user data directory for the DB and config, stored as ``.devops`` in the
    user's home directory (same convention as ``.aws`` / ``.m2``)."""
    override = os.getenv("DASHBOARD_DATA_DIR")
    base = Path(override) if override else Path.home() / ".devops"
    base.mkdir(parents=True, exist_ok=True)
    return base


class Settings:
    DATA_DIR: Path = _default_data_dir()
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'devops_dashboard.db').as_posix()}"
    )
    DEFAULT_AWS_REGION: str = os.getenv("DEFAULT_AWS_REGION", "us-east-1")
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
