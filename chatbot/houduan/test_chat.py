"""进程内接口测试，不访问网络、不消耗真实 API Key。

TestClient 只证明 FastAPI 路由、请求校验、上游调用参数和错误映射的逻辑正确；
它不监听 8000 端口，因此不能替代“服务真的在监听”的验收。真实监听请用
uvicorn 启动后访问 /docs，或运行 check_deepseek_live.py（需要真实 Key）。
"""

import httpx
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
    return TestClient(main.app)


def _fake_response(url: str, status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("POST", url),
    )


def test_chat_interface(client, monkeypatch):
    captured = {}

    async def fake_post(self, url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _fake_response(
            url,
            200,
            {"choices": [{"message": {"content": "你好，这是测试回复"}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 200
    assert response.json() == {"reply": "你好，这是测试回复"}
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert captured["json"]["model"] == "deepseek-chat"
    assert captured["json"]["messages"] == [{"role": "user", "content": "你好"}]


def test_missing_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_upstream_401_returns_readable_error(client, monkeypatch, capsys):
    async def fake_post(self, url, **kwargs):
        return _fake_response(url, 401, {"error": {"message": "invalid key"}})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 401
    assert "401" in response.json()["detail"]
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]
    log = capsys.readouterr().err
    assert "[upstream] 401" in log
    assert "invalid key" in log
    assert "test-key-not-real" not in log


def test_upstream_5xx_returns_502(client, monkeypatch, capsys):
    async def fake_post(self, url, **kwargs):
        return _fake_response(url, 503, {"error": {"message": "unavailable"}})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 502
    assert "503" in response.json()["detail"]
    log = capsys.readouterr().err
    assert "[upstream] 503" in log
    assert "unavailable" in log


def test_timeout_returns_504(client, monkeypatch, capsys):
    async def fake_post(self, url, **kwargs):
        raise httpx.ReadTimeout("timed out", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 504
    assert "超时" in response.json()["detail"]
    assert "[upstream] timeout" in capsys.readouterr().err


def test_connect_error_returns_503(client, monkeypatch, capsys):
    async def fake_post(self, url, **kwargs):
        raise httpx.ConnectError(
            "connection refused",
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 503
    assert "无法连接" in response.json()["detail"]
    assert "[upstream] connect_error" in capsys.readouterr().err


def test_malformed_upstream_payload_returns_502(client, monkeypatch, capsys):
    async def fake_post(self, url, **kwargs):
        return _fake_response(url, 200, {"unexpected": "shape"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post("/chat", json={"message": "你好"})

    assert response.status_code == 502
    assert "格式异常" in response.json()["detail"]
    log = capsys.readouterr().err
    assert "[upstream] 200 parse_error:KeyError" in log
    assert "unexpected" in log


def test_cors_allows_file_origin_null(client):
    response = client.options(
        "/chat",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
