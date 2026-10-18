# 数据流说明

## 证据类型：description

用户在 `chatbot/qinduan/index.html` 点击“发送”后，① 前端读取输入框内容，先把用户消息追加到 `#msgList` 并执行 `msgList.scrollTop = msgList.scrollHeight`，再用 `fetch` 以 `POST` 向 `http://127.0.0.1:8000/chat` 提交 `Content-Type: application/json` 的 JSON `{"message": "用户输入"}`；② 后端 FastAPI 的 `POST /chat` 路由用 `ChatReq` 接收并校验 `message`，`_get_api_key()` 从 `load_dotenv(ENV_PATH)` 载入的 `.env`/进程环境中读取 `DEEPSEEK_API_KEY`（为空时直接返回 503），随后拼装 `Authorization: Bearer <key>` 与 `Content-Type: application/json`，并构造 `{"model": "deepseek-chat", "messages": [{"role": "user", "content": message}]}`；③ 后端用 `httpx.AsyncClient(timeout=30)` 向 `https://api.deepseek.com/v1/chat/completions` 发起 POST，并用 `raise_for_status()` 检查上游状态；④ 成功后读取 `res_data["choices"][0]["message"]["content"]`（即 `choices[0].message.content`），以 JSON `{"reply": content}` 返回；⑤ 前端解析响应，`res.ok` 为 true 时把 `data.reply` 追加到 `#msgList` 并再次执行 `msgList.scrollTop = msgList.scrollHeight`，为 false 时显示 `data.detail`；错误分支包括 401（Key 无效）、402（余额不足）、429（请求过于频繁）、超时 504、连接失败 503、其他 4xx/5xx 与响应结构异常 502、本地缺少 Key 503；服务端为这些上游异常写 `[upstream]` 诊断日志（状态码加截断的响应体，Key 已脱敏），前端捕获网络异常时显示“请求失败：后端服务未启动或网络连接异常”并同样滚动到底部。

`load_dotenv(ENV_PATH)` 只在模块导入时执行，修改 `.env` 后需要重启 uvicorn。

## 本地启动

```powershell
cd chatbot/houduan
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-...
uvicorn main:app --reload --port 8000
```

macOS / Linux 用 `cp .env.example .env` 代替 `copy`。

页面可直接双击 `chatbot/qinduan/index.html` 以 `file://` 打开；也可以用本地静态服务：

```powershell
python -m http.server 8080 --directory chatbot/qinduan
```

然后打开 `http://127.0.0.1:8080/index.html`。两种方式都请求同一个 `http://127.0.0.1:8000/chat`。
