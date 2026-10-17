import httpx
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = "https://api.deepseek.com"
API_KEY = os.getenv("DEEPSEEK_API_KEY")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

body = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "user", "content": "你好"}
    ]
}

r = httpx.post(
    f"{BASE_URL}/v1/chat/completions",
    headers=headers,
    json=body,
    timeout=30
)
print("状态码：", r.status_code)
print("返回内容：", r.json())