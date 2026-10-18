"""手动联调脚本：真实调用 DeepSeek，需要有效 Key 和可用网络。

这个脚本不属于 pytest 自动化测试，避免离线复现时被网络和真实 Key 卡住。
用法：cd chatbot/houduan && python check_deepseek_live.py
"""

from pathlib import Path
import os

import httpx
from dotenv import load_dotenv


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("未找到 DEEPSEEK_API_KEY，请先在 chatbot/houduan/.env 中配置。")

    response = httpx.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "你好"}],
        },
        timeout=30,
    )
    print("状态码：", response.status_code)
    print("返回内容：", response.json())


if __name__ == "__main__":
    main()
