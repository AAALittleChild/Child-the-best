"""Tool declarations and implementations for the course project."""

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().with_name(".env")
MAX_FILE_LINES = 200
BINARY_REPLACEMENT_THRESHOLD = 0.05

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
    },
    {
        "type": "function",
        "function": {
            "name": "get_repo_info",
            "description": "获取 GitHub 公开仓库的语言、Star 数、简介和更新时间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "仓库所有者，例如 openai。",
                    },
                    "repo": {
                        "type": "string",
                        "description": "仓库名称，例如 openai-python。",
                    },
                },
                "required": ["owner", "repo"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_content",
            "description": "读取 GitHub 公开仓库中的文本文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "仓库所有者，例如 openai。",
                    },
                    "repo": {
                        "type": "string",
                        "description": "仓库名称，例如 openai-python。",
                    },
                    "path": {
                        "type": "string",
                        "description": "文件在仓库中的路径，例如 requirements.txt。",
                    },
                },
                "required": ["owner", "repo", "path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出 GitHub 仓库指定目录中的文件和子目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "仓库所有者，例如 openai。",
                    },
                    "repo": {
                        "type": "string",
                        "description": "仓库名称，例如 openai-python。",
                    },
                    "path": {
                        "type": "string",
                        "description": "目录路径；留空表示仓库根目录。",
                    },
                },
                "required": ["owner", "repo"],
                "additionalProperties": False,
            },
        },
    },
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


def get_repo_info(owner: str, repo: str) -> dict[str, Any]:
    """Return a compact summary of a GitHub repository."""
    from github_client import GitHubClient

    owner_path = quote(owner.strip(), safe="")
    repo_path = quote(repo.strip(), safe="")
    if not owner_path or not repo_path:
        return {
            "ok": False,
            "code": 400,
            "error": "owner 和 repo 都不能为空。",
        }

    url = f"https://api.github.com/repos/{owner_path}/{repo_path}"
    with GitHubClient() as client:
        result = client.get(url)

    if not result["ok"]:
        return result

    data = result["data"]
    return {
        "ok": True,
        "code": result["code"],
        "result": {
            "language": data.get("language"),
            "stars": data.get("stargazers_count"),
            "description": data.get("description"),
            "default_branch": data.get("default_branch"),
            "updated_at": data.get("updated_at"),
        },
    }


def get_file_content(owner: str, repo: str, path: str) -> dict[str, Any]:
    """Return decoded text content from a file in a GitHub repository."""
    from github_client import GitHubClient

    owner_path = quote(owner.strip(), safe="")
    repo_path = quote(repo.strip(), safe="")
    file_path = quote(path.strip(), safe="/")
    if not owner_path or not repo_path or not file_path:
        return {
            "ok": False,
            "code": 400,
            "error": "owner、repo 和 path 都不能为空。",
        }

    url = (
        f"https://api.github.com/repos/{owner_path}/{repo_path}"
        f"/contents/{file_path}"
    )
    with GitHubClient() as client:
        result = client.get(url)

    if not result["ok"]:
        if result.get("code") == 404:
            return {
                "ok": False,
                "code": 404,
                "error": "（文件不存在）",
            }
        return result

    encoded_content = result["data"]["content"]
    raw_content = base64.b64decode(encoded_content)
    if not raw_content:
        return {
            "ok": True,
            "code": result["code"],
            "result": {
                "path": path,
                "content": "（文件为空）",
                "total_lines": 0,
                "truncated": False,
                "empty": True,
            },
        }

    # A NUL byte is a cheap, deterministic binary signal. For payloads without
    # NUL, more than 5% replacement characters means UTF-8 decoding failed for
    # most of the data, which is more consistent with binary content.
    if b"\x00" in raw_content:
        return {
            "ok": False,
            "code": 415,
            "error": "（二进制文件，无法作为文本读取）",
        }

    content = raw_content.decode(
        "utf-8",
        errors="replace",
    )
    replacement_ratio = content.count("\ufffd") / len(content)
    if replacement_ratio > BINARY_REPLACEMENT_THRESHOLD:
        return {
            "ok": False,
            "code": 415,
            "error": "（二进制文件，无法作为文本读取）",
        }

    lines = content.splitlines()
    total_lines = len(lines)
    truncated = total_lines > MAX_FILE_LINES
    if truncated:
        content = (
            "\n".join(lines[:MAX_FILE_LINES])
            + f"\n（已截断，仅显示前 {MAX_FILE_LINES} 行，共 {total_lines} 行）"
        )

    return {
        "ok": True,
        "code": result["code"],
        "result": {
            "path": path,
            "content": content,
            "total_lines": total_lines,
            "truncated": truncated,
            "empty": False,
        },
    }


def list_files(owner: str, repo: str, path: str = "") -> dict[str, Any]:
    """List files and directories under a GitHub repository path."""
    from github_client import GitHubClient

    owner_path = quote(owner.strip(), safe="")
    repo_path = quote(repo.strip(), safe="")
    directory_path = quote(path.strip(), safe="/")
    if not owner_path or not repo_path:
        return {
            "ok": False,
            "code": 400,
            "error": "owner 和 repo 都不能为空。",
        }

    url = f"https://api.github.com/repos/{owner_path}/{repo_path}/contents"
    if directory_path:
        url += f"/{directory_path}"

    with GitHubClient() as client:
        result = client.get(url)

    if not result["ok"]:
        return result

    data = result["data"]
    if not isinstance(data, list):
        return {
            "ok": False,
            "code": 422,
            "error": "目标路径不是目录，无法列出文件。",
        }

    entries = [
        {
            "name": item.get("name"),
            "path": item.get("path"),
            "type": item.get("type"),
            "size": item.get("size"),
        }
        for item in data
    ]
    return {
        "ok": True,
        "code": result["code"],
        "result": {
            "path": path or "/",
            "entries": entries,
        },
    }


TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_current_time": get_current_time,
    "get_repo_info": get_repo_info,
    "get_file_content": get_file_content,
    "list_files": list_files,
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

    if "ok" in result:
        return result

    return {"ok": True, "result": result}
