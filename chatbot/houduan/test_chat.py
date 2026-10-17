from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

def test_chat_interface():
    response = client.post("/chat", json={"message": "你好"})
    assert response.status_code == 200
    resp_data = response.json()
    assert "reply" in resp_data