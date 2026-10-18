"""Manual end-to-end check against the running local backend.

Requires:
1. A real DEEPSEEK_API_KEY in chatbot/houduan/.env
2. uvicorn main:app --port 8000 running in another terminal

Usage:
    cd chatbot/houduan
    python check_real_chat.py
"""

from pathlib import Path
import os

import httpx
from dotenv import load_dotenv


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        raise SystemExit(
            "未找到 DEEPSEEK_API_KEY：请先在 chatbot/houduan/.env 中配置真实 Key。"
        )

    response = httpx.post(
        "http://127.0.0.1:8000/chat",
        json={"message": "你好"},
        timeout=60,
    )
    print("状态码：", response.status_code)
    print("返回内容：", response.text)
    response.raise_for_status()
    print("reply：", response.json().get("reply"))


if __name__ == "__main__":
    main()
