from fastapi import FastAPI
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://api.deepseek.com"
API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL_NAME = "deepseek-chat"

if API_KEY is None:
    print("⚠️ 警告：API_KEY读取失败，是None！检查.env文件、路径、变量名")
else:
    print(f"✅ API_KEY读取成功，前缀：{API_KEY[:8]}...")


class ChatReq(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatReq):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": req.message}
        ]
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload)
        res_data = resp.json()
    answer = res_data["choices"][0]["message"]["content"]
    return {"reply": answer}