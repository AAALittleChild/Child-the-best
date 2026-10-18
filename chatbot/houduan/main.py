from pathlib import Path
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# 固定从 main.py 所在目录读取 .env，避免因启动目录不同而读不到 Key。
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

app = FastAPI(title="Chatbot API")

# 本地演示用：前端以 file:// 打开时浏览器发送的 Origin 是 null，
# 这里放开所有来源才能让该页面访问 127.0.0.1:8000。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
TIMEOUT_SECONDS = 30


class ChatReq(BaseModel):
    message: str


def _log_upstream(status: object, text: object = "", kind: str = "") -> None:
    """Print one-line upstream diagnostics without copying into the HTTP reply."""
    body = str(text)[:200].replace("\r", " ").replace("\n", " ")
    prefix = f"[upstream] {status}"
    if kind:
        prefix += f" {kind}"
    print(f"{prefix} {body}".rstrip(), flush=True)


def _get_api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。",
        )
    return api_key


@app.post("/chat")
async def chat(req: ChatReq):
    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": req.message}],
    }

    resp: Optional[httpx.Response] = None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            res_data = resp.json()
        answer = res_data["choices"][0]["message"]["content"]
    except httpx.TimeoutException as exc:
        _log_upstream("timeout", exc)
        raise HTTPException(
            status_code=504,
            detail=f"调用大模型超时（{TIMEOUT_SECONDS} 秒），请稍后重试。",
        ) from exc
    except httpx.ConnectError as exc:
        _log_upstream("connect_error", exc)
        raise HTTPException(
            status_code=503,
            detail="无法连接大模型服务，请检查本机网络或代理设置。",
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        _log_upstream(status, exc.response.text)
        if status == 401:
            detail = "大模型服务鉴权失败（401）：DEEPSEEK_API_KEY 无效或已失效。"
        elif status == 402:
            detail = "大模型账户余额不足（402），请充值后重试。"
        elif status == 429:
            detail = "请求过于频繁（429），请稍后重试。"
        elif 400 <= status < 500:
            detail = f"大模型服务拒绝了请求（{status}），请检查请求参数或账户状态。"
        else:
            detail = f"大模型服务暂时不可用（{status}），请稍后重试。"
        # 上游 5xx 统一转成 502，避免让前端误以为本服务自身崩溃。
        client_status = status if 400 <= status < 500 else 502
        raise HTTPException(status_code=client_status, detail=detail) from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        _log_upstream(
            getattr(resp, "status_code", "unknown"),
            getattr(resp, "text", ""),
            f"parse_error:{type(exc).__name__}",
        )
        raise HTTPException(
            status_code=502,
            detail="大模型返回格式异常，未能解析出回复内容。",
        ) from exc
    except httpx.HTTPError as exc:
        _log_upstream("http_error", exc)
        raise HTTPException(
            status_code=502,
            detail="调用大模型服务失败，请稍后重试。",
        ) from exc

    return {"reply": answer}
