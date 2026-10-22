"""Shared helpers for the course project."""

import os
from pathlib import Path

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().with_name(".env")


def load_environment() -> None:
    """Load environment variables from the project's .env file."""
    load_dotenv(ENV_PATH)


def get_github_token() -> str | None:
    """Return the configured GitHub token, if any."""
    load_environment()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    return token or None


def get_deepseek_api_key() -> str | None:
    """Return the configured DeepSeek API key, if any."""
    load_environment()
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    return api_key or None
