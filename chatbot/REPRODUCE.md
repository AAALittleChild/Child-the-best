# 聊天机器人本地复现与验收说明

本文按仓库的真实目录和真实代码编写。复现路径、启动命令、测试性质、错误边界和前端行为都以当前代码为准。

> 证据类型：description（实现说明）、runtime（实际启动与访问记录）、test（pytest 结果）。
> Evidence tags: description, runtime, test.

原始命令输出文本见 [chatbot/docs/runtime-evidence.txt](docs/runtime-evidence.txt)。
rb_link_2 评审证据汇总见 [chatbot/docs/rb_link_2_evidence.md](docs/rb_link_2_evidence.md)。

## 1. 实际目录结构

```text
Child-the-best/
├─ README.md                   # 项目入口与证据链接
└─ chatbot/
   ├─ houduan/                  # 后端，启动目录
   │  ├─ main.py                # FastAPI 应用
   │  ├─ test_chat.py           # pytest 离线接口测试
   │  ├─ check_deepseek_live.py # 直连 DeepSeek 的手动联调脚本（不参与 pytest）
   │  ├─ check_real_chat.py     # 经本地 /chat 的真实端到端联调脚本
   │  ├─ requirements.txt
   │  ├─ .env.example           # 变量名占位模板，可提交
   │  └─ .env                   # 本地真实 Key，不提交
   ├─ qinduan/
   │  └─ index.html             # 前端页面，用 file:// 直接打开
   ├─ docs/
   │  ├─ rb_link_2_evidence.md   # 评审用运行与排查证据汇总
   │  └─ runtime-evidence.txt   # 原始运行文本证据
   └─ REPRODUCE.md
```

注意：后端代码在 `chatbot/houduan`，前端代码在 `chatbot/qinduan`，不是把 `main.py` 和 `index.html` 放在同一个目录。

## 2. 前置条件

1. Python 3.9 及以上。
2. 仅“真实调用大模型”和 `check_deepseek_live.py` 需要可用的 DeepSeek API Key 与外网；`pytest` 离线测试不需要。

## 3. 配置 API Key

`.env` 必须放在 `chatbot/houduan/`，与 `main.py` 同级。`main.py` 使用下面的方式显式读取该文件，因此不依赖启动时的工作目录：

```python
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)
```

Windows 下复制模板：

```powershell
cd chatbot/houduan
copy .env.example .env
```

macOS / Linux：

```bash
cd chatbot/houduan
cp .env.example .env
```

然后编辑 `.env`，只保留一个变量：

```dotenv
DEEPSEEK_API_KEY=sk-你的真实Key
```

`.env.example` 里只有占位值 `sk-your-deepseek-api-key`，不含真实 Key。

### Key 未泄露的自证

仓库根目录的 `.gitignore` 已包含 `.env`，并显式放行 `.env.example`：

```text
.env
.env.*
!.env.example
```

可用以下命令核对：

```powershell
git ls-files | findstr /i ".env"
git check-ignore -v chatbot/houduan/.env
git check-ignore -q --no-index chatbot/houduan/.env.example
Write-Output "EXAMPLE_IGNORED_EXIT=$LASTEXITCODE"
```

实际结果：

- `git ls-files` 中没有任何 `.env` 文件，只有 `chatbot/houduan/.env.example`。
- `git check-ignore -v chatbot/houduan/.env` 输出 `.gitignore:2:.env`，说明真实 `.env` 被忽略。
- `.env.example` 的忽略检查输出 `EXAMPLE_IGNORED_EXIT=1`，说明它没有被忽略，会正常进入版本库。

同时，仓库中误提交的 `chatbot/houduan/__pycache__/` 已从 Git 索引移除，并加入 `.gitignore`。

## 4. 安装依赖

```powershell
cd chatbot/houduan
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

macOS / Linux 的激活命令为 `source .venv/bin/activate`。

## 5. 启动后端

必须先进入 `chatbot/houduan`，再执行：

```powershell
uvicorn main:app --port 8000
```

需要改代码后自动重载时，可加 `--reload`：

```powershell
uvicorn main:app --reload --port 8000
```

正常启动后，终端会显示类似：

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

验证服务真的在监听（不是进程内测试）：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/docs -UseBasicParsing
```

预期 HTTP 200，并能在浏览器打开 FastAPI 的 `/docs` 页面。

也可以在服务启动后发一次真实请求：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"你好"}'
```

成功时返回：

```json
{"reply": "大模型生成的回答"}
```

### 5.1 实际运行记录（runtime）

以下为本机实际执行记录（Windows，Python 3.14.6，uvicorn 0.40.0）。

启动后端：

```powershell
cd chatbot/houduan
uvicorn main:app --port 8000
```

终端实际输出：

```text
INFO:     Started server process [23620]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

另开一个终端确认 8000 端口在监听：

```powershell
netstat -ano | findstr :8000
Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet
```

实际输出：

```text
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       23620
True
```

访问接口文档：

```powershell
(Invoke-WebRequest -Uri http://127.0.0.1:8000/docs -UseBasicParsing).StatusCode
```

实际输出：

```text
200
```

在没有配置 Key 的情况下请求 `/chat`，用于确认错误路径：

```powershell
curl.exe -i -X POST "http://127.0.0.1:8000/chat" `
  -H "Content-Type: application/json" `
  -d '{"message":"你好"}'
```

实际输出：

```text
HTTP/1.1 503 Service Unavailable
{"detail":"后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。"}
```

CORS 预检（模拟 `file://` 页面的 `Origin: null`）：

```powershell
curl.exe -i -X OPTIONS "http://127.0.0.1:8000/chat" `
  -H "Origin: null" `
  -H "Access-Control-Request-Method: POST" `
  -H "Access-Control-Request-Headers: content-type"
```

实际输出：

```text
HTTP/1.1 200 OK
access-control-allow-origin: *
```

以上是真实 uvicorn 进程、真实 8000 端口和真实 HTTP 请求的结果，不是 `TestClient` 的进程内结果。

### 5.2 前端端到端运行记录（本地桩上游）

为了在不消耗真实 DeepSeek 额度、不依赖外网的情况下验证完整链路，本次使用了一个临时本地桩上游（只用于测试，未提交到仓库）：

- 桩上游监听 `http://127.0.0.1:9001/v1/chat/completions`，返回 `{"choices":[{"message":{"content":"本地桩回复：收到「...」"}}]}`。
- 后端测试入口把 `main.BASE_URL` 指向该桩上游，并设置临时 `DEEPSEEK_API_KEY=dummy-key-for-local-stub`。
- 前端用 `python -m http.server 8080 --directory chatbot/qinduan` 提供同一份 `index.html`。这只是把打开方式从 `file://` 换成 `http://127.0.0.1:8080`，页面代码没有变化。

桩上游和测试入口是一次性临时文件，未提交到仓库；这里保留的是实际运行结果。若要复现，可用任意返回 DeepSeek 兼容 JSON 的本地服务替代。

浏览器实际操作结果：

1. 输入 `你好`，点击发送：
   - 页面显示：`你好`
   - 页面显示：`本地桩回复：收到「你好」`
   - 最终版本的 `index.html` 已移除 A/B/C 调试日志；清理前的 Console 原文保留在 `chatbot/docs/runtime-evidence.txt`
2. 停掉 8000 端口后端，刷新页面，再发送 `后端未启动测试`：
   - 页面显示：`请求失败：后端服务未启动或网络连接异常`
   - Console 报 `请求捕获异常： TypeError: Failed to fetch`
3. 重新启动 8000 端口后端，刷新页面，发送 `恢复测试`：
   - 页面显示：`本地桩回复：收到「恢复测试」`
   - 页面恢复显示回复，说明 `/chat` 请求已成功

这个记录证明了页面能发出真实 HTTP 请求、后端能接收并转发、前端能解析并显示回复，且后端不可用时前端有可读提示。真实 DeepSeek 回复仍需配置真实 Key 后运行 `check_real_chat.py` 或 `check_deepseek_live.py`。

## 6. 打开前端

直接双击打开 `chatbot/qinduan/index.html`，浏览器地址栏是 `file:///.../index.html`。不需要另起前端服务器。

前端请求地址是硬编码的，集中在 `index.html` 的这一行：

```javascript
const CHAT_API = 'http://127.0.0.1:8000/chat';
```

**换机器或改后端端口时，要同步修改这一行。** 页面本身不读取环境变量，也不会自动发现新地址。

### 为什么 `file://` 能访问后端

从 `file://` 打开页面时，浏览器发出的 `Origin` 是 `null`。后端当前配置为：

```python
allow_origins=["*"]
```

因此预检请求会放行。实测 `OPTIONS /chat` 带 `Origin: null` 时返回：

```text
HTTP/1.1 200 OK
access-control-allow-origin: *
```

这个配置是为本地演示放开的；如果以后部署到公网，应改成明确的前端来源白名单。

### 消息滚动

消息列表 `#msgList` 固定高度 `400px`，并设置 `overflow-y: auto`。无论是追加用户消息、机器人回复还是错误提示，代码都会在追加后执行：

```javascript
msgList.scrollTop = msgList.scrollHeight;
```

因此消息变多后可以上下滚动，最新一条始终贴底。

## 7. 测试说明与证据

### 7.1 `test_chat.py` 是什么测试

`test_chat.py` 使用 `fastapi.testclient.TestClient`，是**进程内测试**：

- 不监听 `127.0.0.1:8000`，不经过真实网络端口；
- 不使用真实 `DEEPSEEK_API_KEY`；
- 不访问 DeepSeek。测试通过 `pytest` 的 `monkeypatch` 把 `httpx.AsyncClient.post` 替换为本地假函数，返回构造好的 DeepSeek 响应；
- 覆盖成功回复、缺少 Key、上游 401、上游 5xx、超时、连接失败、返回格式异常，以及 `file://` 的 `Origin: null` 预检，共 8 项。

它证明的是：路由、请求体校验、转发给 DeepSeek 的 URL/Header/模型参数、响应解析和错误映射的逻辑正确。它**不能**证明 8000 端口真的在监听；后者由第 5 节的 uvicorn + `/docs` 验证。

运行方式：

```powershell
cd chatbot/houduan
python -m pytest -v
```

实际结果：

```text
collected 8 items
test_chat.py::test_chat_interface PASSED
test_chat.py::test_missing_key_returns_503 PASSED
test_chat.py::test_upstream_401_returns_readable_error PASSED
test_chat.py::test_upstream_5xx_returns_502 PASSED
test_chat.py::test_timeout_returns_504 PASSED
test_chat.py::test_connect_error_returns_503 PASSED
test_chat.py::test_malformed_upstream_payload_returns_502 PASSED
test_chat.py::test_cors_allows_file_origin_null PASSED
8 passed
```

### 7.2 真实联调脚本

`check_deepseek_live.py` 是手动脚本，不是 pytest 用例。它会真实访问 DeepSeek，需要有效 Key 和网络：

```powershell
cd chatbot/houduan
python check_deepseek_live.py
```

它被单独命名并放在 `if __name__ == "__main__":` 保护下，因此运行 `pytest` 时不会被收集，也不会偷偷发起真实请求。

### 7.3 真实监听与无 Key 错误提示的实测

启动 uvicorn 后实测：

```text
GET  /docs  -> 200
POST /chat  -> 503
{"detail":"后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。"}
```

这说明端口确实在监听，且缺少 Key 时返回的是可读 JSON，而不是 500 堆栈。

### 7.4 真实 Key 的端到端验证（需本机配置）

先按第 3 节把真实 Key 写入 `chatbot/houduan/.env`，再启动后端：

```powershell
cd chatbot/houduan
uvicorn main:app --port 8000
```

另开一个终端，运行：

```powershell
cd chatbot/houduan
python check_real_chat.py
```

它发送的是与页面完全相同的 `POST http://127.0.0.1:8000/chat`，因此验证的是“前端同款请求 → 本地后端 → DeepSeek → 返回”的完整链路。

本次使用真实 Key 实测（2026-10-18），实际输出：

```text
状态码： 200
返回内容： {"reply":"你好！很高兴见到你，有什么我可以帮你的吗？无论是聊天、解答问题，还是需要一些建议，我都在这里。😊"}
reply： 你好！很高兴见到你，有什么我可以帮你的吗？无论是聊天、解答问题，还是需要一些建议，我都在这里。😊
```

这条回复来自真实 DeepSeek，不是本地桩上游。Key 只从本机 `.env` 读入进程环境，没有写入仓库或证据文件。

完整评审版（含启动、访问地址、报错原文和三步定位）见 [chatbot/docs/rb_link_2_evidence.md](docs/rb_link_2_evidence.md)。

若没有配置 Key，脚本会直接退出并提示先配置 `DEEPSEEK_API_KEY`，不会发出真实请求。

## 8. 异常处理与边界

后端当前的错误映射如下，均为 JSON `{"detail": "..."}` 形式：

| 场景 | HTTP 状态码 | 提示内容 |
| --- | --- | --- |
| 本地未配置 `DEEPSEEK_API_KEY` | 503 | 提示在 `chatbot/houduan/.env` 中填写 |
| DeepSeek 返回 401 | 401 | Key 无效或已失效 |
| DeepSeek 返回 402 | 402 | 账户余额不足 |
| DeepSeek 返回 429 | 429 | 请求过于频繁 |
| DeepSeek 返回其他 4xx | 502 | 上游拒绝了请求，附状态码 |
| DeepSeek 返回 5xx | 502 | 上游暂时不可用，附状态码 |
| 请求 DeepSeek 超时（30 秒） | 504 | 调用超时 |
| 无法连接 DeepSeek | 503 | 检查网络或代理 |
| 返回 JSON 无法解析或缺少字段 | 502 | 返回格式异常 |
| 前端请求体不合法 | 422 | FastAPI 自动校验提示 |
| 前端完全连不上本服务 | 无 HTTP 响应 | 页面显示“请求失败：后端服务未启动或网络连接异常” |

前端会先判断 `res.ok`：成功时显示 `data.reply`，失败时显示后端返回的 `data.detail`，不会再把错误响应当成正常回复显示成 `undefined`。

### 服务端上游日志

所有上游异常都会在终端留下 `[upstream]` 行，例如：

```text
[upstream] 401 {"error":{"message":"invalid key"}}
```

- HTTP 状态错误：`[upstream] <status> <响应体前 200 字符，换行替换为空格>`
- 超时：`[upstream] timeout <异常文本>`
- 连接失败：`[upstream] connect_error <异常文本>`
- 响应解析失败：`[upstream] <status> parse_error:<异常类型> <响应体前 200 字符，换行替换为空格>`
- 其他传输错误：`[upstream] http_error <异常文本>`

日志只打印状态码和截断后的响应体，不打印 `Authorization` 头或 API Key。使用 `print(..., file=sys.stderr, flush=True)`，与 uvicorn 的 INFO 日志走同一个终端流，避免只采集 stderr 时漏掉。

仍需如实说明的边界：

- 没有自动重试；超时或上游 5xx 需要用户手动重发。
- 没有流式输出，必须等完整回复返回后一次性显示。
- 没有多轮上下文；每次请求只把当前这一条 `message` 发给 DeepSeek，之前的对话不会带入。
- 本服务自身没有登录、鉴权和限流，CORS 为本地演示放开了 `*`，不适合直接公网部署。
- `check_deepseek_live.py` 只打印上游状态码和响应，不负责自动判定内容质量。

## 9. 三步排查

打开浏览器开发者工具，按 F12：

1. **Network**：找到 `/chat` 请求，成功时 Status 为 200；若为 4xx/5xx，查看 Response 里的 `detail`。
2. **Console**：如果请求没有到达后端，会看到 `请求捕获异常： TypeError: Failed to fetch`。
3. **判断方向**：`Failed to fetch` 通常是后端未启动、端口不对，或前端 `CHAT_API` 与本机地址不一致；如果出现 CORS 相关报错，检查 `file://` 页面的 `Origin: null` 是否被 `allow_origins=["*"]` 放行。

### 9.1 本次真实报错排查记录

完整的评审版（含启动命令、访问地址、报错原文、三步定位和最终真实回复）见 [chatbot/docs/rb_link_2_evidence.md](docs/rb_link_2_evidence.md)。

现象：停掉后端后，从页面发送消息，页面显示“请求失败：后端服务未启动或网络连接异常”，Console 报：

```text
请求捕获异常： TypeError: Failed to fetch
```

排查顺序：

1. **后端端口是否在监听**：

   ```powershell
   netstat -ano | findstr :8000
   ```

   后端停止时没有 `LISTENING` 行；启动后出现：

   ```text
   TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       23620
   ```

   结论：`Failed to fetch` 的直接原因是 8000 端口没有服务监听。

2. **前端 `CHAT_API` 是否一致**：打开 `index.html`，确认：

   ```javascript
   const CHAT_API = 'http://127.0.0.1:8000/chat';
   ```

   它与后端实际监听地址 `127.0.0.1:8000` 一致。如果后端换端口或换机器，必须同步改这一行，否则仍会 `Failed to fetch`。

3. **CORS 是否放行**：`file://` 页面的 `Origin` 是 `null`。用 `curl` 模拟预检：

   ```powershell
   curl.exe -i -X OPTIONS "http://127.0.0.1:8000/chat" `
     -H "Origin: null" `
     -H "Access-Control-Request-Method: POST"
   ```

   当前 `allow_origins=["*"]` 返回：

   ```text
   HTTP/1.1 200 OK
   access-control-allow-origin: *
   ```

   因此浏览器不会因 CORS 拦截。如果删除该中间件或改成不包含 `null` 的白名单，浏览器会报 `No 'Access-Control-Allow-Origin' header is present on the requested resource.`，页面同样会进入 catch 分支。

4. **恢复**：重新启动 `uvicorn main:app --port 8000`，刷新页面，再发送消息，页面恢复显示回复。

另一个已修复的真实代码错误：

- 原 `main.py` 没有 `raise_for_status()`。DeepSeek 返回 401 时，响应体是 `{"error": ...}`，没有 `choices`，执行 `res_data["choices"]` 会抛 `KeyError: 'choices'`，FastAPI 最终返回 500。
- 修复：先 `resp.raise_for_status()`，再捕获 `httpx.HTTPStatusError`，按状态码返回 401/402/429 或 502，并给出可读 `detail`。
- 回归测试：`test_upstream_401_returns_readable_error` 和 `test_upstream_5xx_returns_502` 均通过。

## 10. 最短验收清单

- [ ] `cd chatbot/houduan && python -m pytest -q`，8 项通过。
- [ ] `uvicorn main:app --port 8000` 启动后，`http://127.0.0.1:8000/docs` 返回 200。
- [ ] 双击 `chatbot/qinduan/index.html`，输入消息能收到回复。
- [ ] 消息超过列表高度后可滚动，最新消息贴底。
- [ ] `git ls-files` 中没有 `.env`，`.gitignore` 忽略 `.env`，`.env.example` 已提交。
- [ ] 改动端口或换机器时，已同步修改 `index.html` 中的 `CHAT_API`。
