"""Tool declarations and implementations for the course project."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().with_name(".env")

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取用户电脑当前所在时区的日期和时间。",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }
]


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


def get_current_time() -> dict[str, str]:
    """Return the current local date and time."""
    now = datetime.now().astimezone()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": now.tzname() or str(now.tzinfo),
        "iso": now.isoformat(timespec="seconds"),
    }


TOOL_HANDLERS: dict[str, Callable[..., dict[str, str]]] = {
    "get_current_time": get_current_time,
}


def execute_tool(name: str, arguments_json: str) -> dict[str, Any]:
    """Execute a declared tool and return a JSON-serializable result."""
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"未知工具：{name}"}

    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"工具参数不是有效 JSON：{exc.msg}"}

    if not isinstance(arguments, dict):
        return {"ok": False, "error": "工具参数必须是 JSON 对象。"}

    try:
        result = handler(**arguments)
    except TypeError as exc:
        return {"ok": False, "error": f"工具参数不匹配：{exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"工具执行失败：{exc}"}

    return {"ok": True, "result": result}
