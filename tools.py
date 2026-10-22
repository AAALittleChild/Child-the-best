"""Shared helpers for the course project."""

import os
from pathlib import Path

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().with_name(".env")


def get_github_token() -> str | None:
    """Load the project's .env file and return the configured token."""
    load_dotenv(ENV_PATH)
    token = os.getenv("GITHUB_TOKEN", "").strip()
    return token or None
