# rb_link_2 运行与排查证据

- 项目：Child-the-best / chatbot
- 采集日期：2026-10-18（Asia/Shanghai）
- 环境：Windows，Python 3.14.6，uvicorn 0.40.0，FastAPI 0.143.3，httpx 0.28.1
- 原始文本证据：[runtime-evidence.txt](runtime-evidence.txt)（第 8 节附完整原文）
- 完整复现说明：[REPRODUCE.md](../REPRODUCE.md)

本文件把真实启动命令、访问地址、报错原文、三步定位过程和最终真实回复集中在一处，供 rb_link_2 直接核对。

## 1. 真实启动命令与访问地址

启动目录必须是 `chatbot/houduan`：

```powershell
cd chatbot/houduan
uvicorn main:app --port 8000
```

实际启动日志：

```text
✅ DEEPSEEK_API_KEY 已配置（值已隐藏）
INFO:     Started server process [30648]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

`✅` 只表示 `DEEPSEEK_API_KEY` 非空且已被读取，不校验 Key 有效性；有效性要到首次真实请求才会暴露（401 无效、402 余额不足）。

`.env.example` 的 Key 行右侧留空；原样复制启动会显示 `⚠️ DEEPSEEK_API_KEY 未配置`，只有填入非空 Key 才显示 `✅`。

端口确认（netstat 来自另一轮运行，PID 会变化）：

```text
netstat -ano | findstr :8000
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       23620

Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet
True
```

访问地址：

- 后端聊天接口：`http://127.0.0.1:8000/chat`
- FastAPI 文档：`http://127.0.0.1:8000/docs`，实测返回 `200`
- 方式 A（日常使用）：双击 `chatbot/qinduan/index.html`，即 `file:///.../chatbot/qinduan/index.html`
- 方式 B（本次页面实测）：`python -m http.server 8080 --directory chatbot/qinduan`，打开 `http://127.0.0.1:8080/index.html`；页面代码没有变化
- 两种方式都由 `allow_origins=["*"]` 放行；方式 A 的 `Origin: null` 已用 curl 预检单独验证

## 2. 遇到的报错原文

后端未启动时，页面显示：

```text
请求失败：后端服务未启动或网络连接异常
```

浏览器 Console 原文（清理 A/B/C 调试日志前的页面）：

```text
请求捕获异常： TypeError: Failed to fetch
    at HTMLButtonElement.<anonymous> (http://127.0.0.1:8080/index.html:40:35)
```

旧版后端还有一个已修复的错误：DeepSeek 返回 401 时，原代码没有 `raise_for_status()`，响应体没有 `choices`，执行 `res_data["choices"]` 会抛：

```text
KeyError: 'choices'
```

最终表现为 500。修复后先调用 `resp.raise_for_status()`，捕获 `httpx.HTTPStatusError`，返回 401 和可读 `detail`。

缺少本地 Key 时的 503 原文：

```text
HTTP/1.1 503 Service Unavailable
{"detail":"后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。"}
```

现在服务端还会为上游异常把诊断行写到 stderr，例如：

```text
[upstream] 401 {"error":{"message":"Authentication Fails, Your api key: **** is invalid",...}}
```

响应体截断到 200 字符，不打印 `Authorization` 头或 API Key；`Your api key: ...`、`api_key=...`、`Bearer ...` 和 `sk-...` 会先脱敏为 `****`。写到 stderr 是为了与 uvicorn 的 INFO 日志走同一采集流，避免只抓 stderr 时漏掉上游原文。

### 2.1 空 Key 的 503 分支实测

前置条件：仓库无 `.env`，当前进程环境无 `DEEPSEEK_API_KEY`，启动全新 uvicorn 进程。启动输出：

```text
⚠️ DEEPSEEK_API_KEY 未配置
INFO:     Started server process [32140]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

页面发送 `空Key分支验证` 后显示：

```text
空Key分支验证
请求失败：后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。
```

后端访问日志：

```text
INFO:     127.0.0.1:60541 - "OPTIONS /chat HTTP/1.1" 200 OK
INFO:     127.0.0.1:60541 - "POST /chat HTTP/1.1" 503 Service Unavailable
```

没有 `[upstream]` 行，因为 `_get_api_key()` 在发出上游请求前就抛了 503。`load_dotenv(ENV_PATH)` 只在模块导入时执行；修改 `.env` 后必须重启 uvicorn，否则旧进程可能仍持有旧 Key。

## 3. 按“后端端口 → 前端地址 → CORS”的三步定位

### 第一步：后端端口是否在监听

```powershell
netstat -ano | findstr :8000
```

后端停止时没有 `LISTENING` 行；启动后出现：

```text
TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       23620
```

`Test-NetConnection` 同时返回 `True`，`/docs` 返回 `200`。因此 `Failed to fetch` 的直接原因是 8000 端口没有服务监听。

### 第二步：前端 `CHAT_API` 是否与后端地址一致

[index.html](../qinduan/index.html) 中硬编码：

```javascript
const CHAT_API = 'http://127.0.0.1:8000/chat';
```

它与后端实际监听地址 `127.0.0.1:8000` 一致。如果后端换端口或换机器，必须同步修改这一行，否则请求仍然会 `Failed to fetch`。

### 第三步：CORS 是否放行 `file://` 的 null Origin

`file://` 页面发出的 `Origin` 是 `null`。后端当前配置：

```python
allow_origins=["*"]
```

用 curl 模拟预检：

```powershell
curl.exe -i -X OPTIONS 'http://127.0.0.1:8000/chat' -H 'Origin: null' -H 'Access-Control-Request-Method: POST'
```

实际响应：

```text
HTTP/1.1 200 OK
access-control-allow-origin: *
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-max-age: 600
```

因此浏览器不会因 CORS 拦截。如果删除 CORS 中间件或改成不包含 `null` 的白名单，浏览器会报 `No 'Access-Control-Allow-Origin' header is present on the requested resource.`，页面会进入同一个 catch 分支。

### 恢复

重新启动：

```powershell
cd chatbot/houduan
uvicorn main:app --port 8000
```

刷新页面后再次发送消息，页面恢复显示回复，说明“端口 → 地址 → CORS”三步都已通过。

## 4. 最终状态码与真实回复

使用真实 `DEEPSEEK_API_KEY` 启动当前仓库的 `main.py` 后，运行：

```powershell
cd chatbot/houduan
python check_real_chat.py
```

实际输出：

```text
状态码： 200
返回内容： {"reply":"你好！很高兴见到你，有什么我可以帮你的吗？无论是聊天、解答问题，还是需要一些建议，我都在这里。😊"}
reply： 你好！很高兴见到你，有什么我可以帮你的吗？无论是聊天、解答问题，还是需要一些建议，我都在这里。😊
```

这条回复来自真实 DeepSeek，经 `POST http://127.0.0.1:8000/chat` 返回，不是本地桩上游。

Key 只从本机 `.env` 读入进程环境，没有写入仓库、证据文件或提交记录。测试使用的是当前仓库已修复的 `main.py`，不是旧版本副本。

### 4.1 页面成功路径（真实 DeepSeek）

这一节不是 401 错误分支，而是页面实际收到机器人回答的成功路径。使用方式 B 打开同一份 `index.html`，输入并发送：

```text
请用一句话介绍你自己
```

页面实际显示：

```text
请用一句话介绍你自己
我是DeepSeek，由深度求索公司创造的AI助手，致力于用热情细腻的方式帮助你探索世界、解决问题。
```

后端终端新增：

```text
INFO:     127.0.0.1:51929 - "OPTIONS /chat HTTP/1.1" 200 OK
INFO:     127.0.0.1:51929 - "POST /chat HTTP/1.1" 200 OK
```

成功路径没有 `[upstream]` 错误行。后端执行了 `res_data["choices"][0]["message"]["content"]`，返回 `{"reply": ...}`，前端再显示 `data.reply`；401 分支不会走到这段取值代码。

辅助截图：[page-success.png](page-success.png)。

成功路径的兜底边界：`chatbot/houduan/main.py:99` 直接取 `res_data["choices"][0]["message"]["content"]`，没有 `.get()`、默认回复、重试或备用模型；缺 `choices`、`message` 或 `content` 时由 `main.py:128` 捕获并返回 `main.py:136` 的 502；`content` 为 `null` 或非字符串时没有非空/类型校验。这里的兜底只是“失败转 502”，不是“成功内容兜底”。

### 4.2 方式 A（`file://`）页面验收（手工）

当前自动化浏览器环境禁止 `file://` 协议，无法在这里生成方式 A 的自动化页面结果，不伪造。手工验收步骤：

1. 按第 1 节启动后端并配置真实 Key。
2. 双击 `chatbot/qinduan/index.html`，地址栏应为 `file:///.../index.html`。
3. 发送 `请用一句话介绍你自己`。
4. 页面应显示该问题和一条机器人回复；DevTools Network 中 `POST /chat` 应为 `200`，Response Headers 含 `access-control-allow-origin: *`，Console 无 CORS 报错。

这一条目前是“手工验收步骤”，不是自动化结果；方式 B 的 H 节是已验证的页面成功路径，不能替代方式 A 的浏览器实测。

## 5. 测试与最终页面状态

```powershell
cd chatbot/houduan
python -m pytest -v
```

实际结果：

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.0.3, pluggy-1.6.0 -- E:\Anaconda\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\jimoq\Documents\Test\Child-the-best\chatbot\houduan
plugins: anyio-4.12.1
collecting ... collected 10 items

test_chat.py::test_chat_interface PASSED                                 [ 10%]
test_chat.py::test_missing_key_returns_503 PASSED                        [ 20%]
test_chat.py::test_upstream_401_returns_readable_error PASSED            [ 30%]
test_chat.py::test_upstream_5xx_returns_502 PASSED                       [ 40%]
test_chat.py::test_upstream_402_returns_readable_error PASSED            [ 50%]
test_chat.py::test_timeout_returns_504 PASSED                            [ 60%]
test_chat.py::test_connect_error_returns_503 PASSED                      [ 70%]
test_chat.py::test_malformed_upstream_payload_returns_502 PASSED         [ 80%]
test_chat.py::test_cors_allows_file_origin_null PASSED                   [ 90%]
test_chat.py::test_frontend_html_has_no_secret_material PASSED           [100%]

============================== warnings summary ===============================
E:\Anaconda\Lib\site-packages\fastapi\testclient.py:1
  E:\Anaconda\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 10 passed, 1 warning in 0.58s ========================
```

10 项包含新增的上游 402 映射测试和前端 HTML 无 Key 静态检查。

清理 A/B/C 调试日志后的页面冒烟测试：

```text
页面显示：请求失败：后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。
Console： []
```

说明最终页面仍能发出请求、读取非 2xx 响应的 `detail` 并显示，且不再输出 A/B/C 调试标记。

### 5.1 消息滚动实测（本地桩上游）

连发 15 条消息，共 30 个消息节点（15 条用户消息 + 15 条机器人回复）：

```text
clientHeight=416, scrollHeight=716, maxScrollTop=300
发送后：scrollTop=300, atBottom=true, 最后一条=收到：滚动测试第 15 条
向上滚一页：scrollTop=0, atBottom=false
向下滚回：scrollTop=300, atBottom=true
```

说明列表内容超过可视高度、可以上下滚动，最新一条在追加后仍贴底。该测试只验证前端滚动，使用本地桩上游，不依赖真实模型。

## 6. 评审项对应关系

| 评审项 | 位置 |
| --- | --- |
| 真实启动命令 | 第 1 节 |
| 访问地址 | 第 1 节 |
| 报错原文 | 第 2 节 |
| 后端端口 → 前端地址 → CORS 三步定位 | 第 3 节 |
| 最终状态码与真实回复 | 第 4 节 |
| 自动化测试与最终页面状态 | 第 5 节 |

## 7. 后续安全建议

`allow_origins=["*"]` 仅用于本地 `file://` 演示。后续部署时应收紧为明确来源，例如只允许实际前端域名；本次按 rb_link_3 的结论不做代码修改。

注意 `allow_origins=["*"]` 与 `allow_credentials=True` 不能共存，将来加登录态时必须改成具体来源白名单。

当前仓库没有 `.github/workflows`，因此本次没有新增 GitHub Actions 工作流；运行证据以本文件和 `runtime-evidence.txt` 的原始输出为准。

## 8. 原始运行文本（runtime-evidence.txt）

以下为 runtime-evidence.txt 的当前完整内容，便于在单一证据文件中核对。

```text
Chatbot runtime evidence
Captured: 2026-10-18 (Asia/Shanghai)
Repository: https://github.com/AAALittleChild/Child-the-best
Environment: Windows, Python 3.14.6, uvicorn 0.40.0, FastAPI 0.143.3, httpx 0.28.1

This file preserves the raw command outputs behind REPRODUCE.md sections 5.1,
5.2, 7 and 9.1. It is text evidence, not a summary written after the fact.

============================================================
A. Backend startup and HTTP checks (REPRODUCE.md 5.1)
============================================================

Command:

    cd chatbot/houduan
    uvicorn main:app --port 8000

Terminal output (stderr):

    ✅ DEEPSEEK_API_KEY 已配置（值已隐藏）
    INFO:     Started server process [23620]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

The ✅ line only means DEEPSEEK_API_KEY is non-empty and was loaded. It does
not validate the key; validity is revealed on the first real request (401 for
invalid key, 402 for insufficient balance).

Empty template check (copy .env.example to .env without editing):

    ⚠️ DEEPSEEK_API_KEY 未配置
    INFO:     Started server process [15512]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

This confirms that copying the empty template unchanged does not produce ✅.

Port check:

    netstat -ano | findstr :8000
      TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       23620

    Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet
    True

FastAPI docs:

    (Invoke-WebRequest -Uri http://127.0.0.1:8000/docs -UseBasicParsing).StatusCode
    200

POST /chat with no DEEPSEEK_API_KEY configured:

    curl.exe -i -X POST 'http://127.0.0.1:8000/chat' -H 'Content-Type: application/json' -d '{"message":"你好"}'

    HTTP/1.1 503 Service Unavailable
    date: Sun, 18 Oct 2026 02:20:17 GMT
    server: uvicorn
    content-length: 103
    content-type: application/json

    {"detail":"后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。"}

CORS preflight with file:// origin null:

    curl.exe -i -X OPTIONS 'http://127.0.0.1:8000/chat' -H 'Origin: null' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'

    HTTP/1.1 200 OK
    date: Sun, 18 Oct 2026 02:20:17 GMT
    server: uvicorn
    access-control-allow-origin: *
    access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
    access-control-max-age: 600
    access-control-allow-headers: content-type
    content-length: 2
    content-type: text/plain; charset=utf-8

    OK

============================================================
B. Frontend end-to-end run (REPRODUCE.md 5.2)
   Captured BEFORE removing the A/B/C debug logs
============================================================

Test setup:

    - Temporary stub upstream: http://127.0.0.1:9001/v1/chat/completions
    - Temporary backend: main.BASE_URL pointed to the stub, dummy test key
    - Frontend served unchanged at http://127.0.0.1:8080/index.html
      (same index.html; only the opening origin differs from file://)

Success case:

    page text: 你好
    page text: 本地桩回复：收到「你好」

    browser console:
    [log 2026-10-18T02:18:19.790Z] 标记A：即将执行fetch
    [log 2026-10-18T02:18:19.836Z] 标记B：fetch返回，拿到res
    [log 2026-10-18T02:18:19.836Z] 标记C：json解析完成

Backend stopped case:

    page text: 请求失败：后端服务未启动或网络连接异常

    browser console:
    [log   2026-10-18T02:18:34.319Z] 标记A：即将执行fetch
    [error 2026-10-18T02:18:34.326Z] 请求捕获异常： TypeError: Failed to fetch
                                     at HTMLButtonElement.<anonymous>
                                     (http://127.0.0.1:8080/index.html:40:35)

Recovery case (backend restarted):

    page text: 恢复测试
    page text: 本地桩回复：收到「恢复测试」

    browser console:
    [log 2026-10-18T02:19:15.851Z] 标记A：即将执行fetch
    [log 2026-10-18T02:19:16.012Z] 标记B：fetch返回，拿到res
    [log 2026-10-18T02:19:16.012Z] 标记C：json解析完成

Note: the final index.html removes the three console.log statements marked
A/B/C. The transcript above is kept as historical runtime evidence. The final
version still keeps console.error for a failed fetch.

============================================================
C. Automated tests (REPRODUCE.md 7)
============================================================

Command:

    cd chatbot/houduan
    python -m pytest -v

Output:

    ============================= test session starts =============================
    platform win32 -- Python 3.14.6, pytest-9.0.3, pluggy-1.6.0 -- E:\Anaconda\python.exe
    cachedir: .pytest_cache
    rootdir: C:\Users\jimoq\Documents\Test\Child-the-best\chatbot\houduan
    plugins: anyio-4.12.1
    collecting ... collected 10 items

    test_chat.py::test_chat_interface PASSED                                 [ 10%]
    test_chat.py::test_missing_key_returns_503 PASSED                        [ 20%]
    test_chat.py::test_upstream_401_returns_readable_error PASSED            [ 30%]
    test_chat.py::test_upstream_5xx_returns_502 PASSED                       [ 40%]
    test_chat.py::test_upstream_402_returns_readable_error PASSED            [ 50%]
    test_chat.py::test_timeout_returns_504 PASSED                            [ 60%]
    test_chat.py::test_connect_error_returns_503 PASSED                      [ 70%]
    test_chat.py::test_malformed_upstream_payload_returns_502 PASSED         [ 80%]
    test_chat.py::test_cors_allows_file_origin_null PASSED                   [ 90%]
    test_chat.py::test_frontend_html_has_no_secret_material PASSED           [100%]

    ============================== warnings summary ===============================
    E:\Anaconda\Lib\site-packages\fastapi\testclient.py:1
      E:\Anaconda\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
        from starlette.testclient import TestClient as TestClient  # noqa

    -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
    ======================== 10 passed, 1 warning in 0.58s ========================

The warning does not change the test result.

============================================================
D. Real DeepSeek reply check (COMPLETED)
============================================================

Initial check before the key was provided:

    DEEPSEEK_API_KEY=NOT_SET
    chatbot/houduan/.env=ABSENT

Then a real key was supplied from the user's local .env. The key was read into
the process environment only; it was not printed, copied into the repository,
or committed.

Command sequence:

    # Start the current backend with DEEPSEEK_API_KEY in its environment.
    cd chatbot/houduan
    uvicorn main:app --port 8000

    # In a second terminal:
    cd chatbot/houduan
    python check_real_chat.py

Actual output:

    状态码： 200
    返回内容： {"reply":"你好！很高兴见到你，有什么我可以帮你的吗？无论是聊天、解答问题，还是需要一些建议，我都在这里。😊"}
    reply： 你好！很高兴见到你，有什么我可以帮你的吗？无论是聊天、解答问题，还是需要一些建议，我都在这里。😊

This is a real DeepSeek response through POST http://127.0.0.1:8000/chat,
not the local stub.

Future reproduction:

    cd chatbot/houduan
    # Windows: copy .env.example .env
    # macOS/Linux: cp .env.example .env
    # edit .env and set DEEPSEEK_API_KEY=sk-...
    uvicorn main:app --port 8000

    # second terminal
    python check_real_chat.py

Direct upstream check:

    cd chatbot/houduan
    python check_deepseek_live.py

============================================================
E. Final post-cleanup smoke test
============================================================

After removing the A/B/C console.log statements from index.html, the page was
served again at http://127.0.0.1:8080/index.html and tested against the backend
with no DEEPSEEK_API_KEY configured.

Page text after clicking 发送 with message "清理后测试":

    清理后测试
    请求失败：后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。

Browser console entries:

    []

This confirms that the final page still sends the request, reads the JSON
detail on a non-2xx response, renders it, and no longer emits A/B/C debug logs.

============================================================
F. Upstream error log verification (live uvicorn)
============================================================

A temporary stub upstream returned HTTP 402 with:

    {"error":{"message":"Insufficient Balance","type":"insufficient_quota"}}

The current backend was started with uvicorn on port 8000. POST /chat returned:

    HTTP/1.1 402 Payment Required
    {"detail":"大模型账户余额不足（402），请充值后重试。"}

Backend stderr (the same stream as uvicorn's INFO logs):

    INFO:     Started server process [28200]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
    [upstream] 402 {"error":{"message":"Insufficient Balance","type":"insufficient_quota"}}

Backend stdout (access log):

    INFO:     127.0.0.1:56061 - "POST /chat HTTP/1.1" 402 Payment Required

The [upstream] line is now written to stderr, so it remains visible when only
the uvicorn error stream is collected. The response body is truncated to 200
characters and the line does not contain the Authorization header or API key.

A separate TestClient probe with a fake 401 also produced:

    [upstream] 401 {"error":{"message":"invalid key"}}
    HTTP 401 {'detail': '大模型服务鉴权失败（401）：DEEPSEEK_API_KEY 无效或已失效。'}

============================================================
G. Live wrong-key 401 verification (redacted)
============================================================

A deliberately wrong test key was used to force a real DeepSeek 401. The
backend startup output was:

    ✅ DEEPSEEK_API_KEY 已配置（值已隐藏）
    INFO:     Started server process [30648]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

After opening the page and clicking 发送 with the message
"验证错误Key（脱敏复测）", the page showed:

    验证错误Key（脱敏复测）
    请求失败：大模型服务鉴权失败（401）：DEEPSEEK_API_KEY 无效或已失效。

The new terminal lines were:

    [upstream] 401 {"error":{"message":"Authentication Fails, Your api key: **** is invalid (request_id: 2a344412-bc50-4535-a8b7-3447bbd500c4)","type":"authentication_error","param":null,"code":"invalid_request_error"}}
    INFO:     127.0.0.1:56925 - "POST /chat HTTP/1.1" 401 Unauthorized

The upstream response echoed a masked key suffix. The application's redaction
replaced it with **** before writing to stderr; the log does not contain the
request Authorization header or the full API key.

============================================================
H. Page success path (real DeepSeek)
============================================================

Access method used for this run:

    python -m http.server 8080 --directory chatbot/qinduan
    http://127.0.0.1:8080/index.html

This is the same index.html as the file:// workflow; only the origin differs.

Backend startup:

    ✅ DEEPSEEK_API_KEY 已配置（值已隐藏）
    INFO:     Started server process [22600]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

Page after sending "请用一句话介绍你自己":

    请用一句话介绍你自己
    我是DeepSeek，由深度求索公司创造的AI助手，致力于用热情细腻的方式帮助你探索世界、解决问题。

Backend access log:

    INFO:     127.0.0.1:51929 - "OPTIONS /chat HTTP/1.1" 200 OK
    INFO:     127.0.0.1:51929 - "POST /chat HTTP/1.1" 200 OK

Screenshot (auxiliary): chatbot/docs/page-success.png

There was no [upstream] error line on this success path. The backend executed
res_data["choices"][0]["message"]["content"] and returned {"reply": ...}; the
page rendered data.reply. The 401 path never reaches this extraction code, so
this run is the success-path evidence rather than another authentication test.

Success-path fallback boundary:

- main.py:99 directly indexes res_data["choices"][0]["message"]["content"];
  there is no .get(), default reply, retry, or backup model.
- Missing/empty choices, missing message, or missing content -> main.py:128
  catches KeyError/IndexError/TypeError/ValueError -> main.py:136 returns
  HTTP 502 "大模型返回格式异常，未能解析出回复内容。"
- If content exists but is null or non-string, there is no non-empty/type
  validation; it is returned as-is and the page may render empty content.

This success run proves the valid response shape works. It does not add a
content-level fallback for a malformed successful response.

============================================================
I. Message list scroll verification (local stub upstream)
============================================================

15 messages were sent, producing 30 child nodes (15 user + 15 bot).

Raw metrics:

    {"atBottom":true,"childCount":30,"clientHeight":416,"lastText":"收到：滚动测试第 15 条","maxScrollTop":300,"scrollHeight":716,"scrollTop":300}

After scrolling up one page:

    {"atBottom":false,"scrollTop":0,"maxScrollTop":300}

After scrolling down in the message area:

    {"atBottom":true,"scrollTop":300,"maxScrollTop":300}

This confirms the message list is scrollable, the latest message is pinned to
the bottom after appending, and the user can scroll up and back down. The test
used a local stub upstream and only exercises frontend scrolling.

============================================================
J. Empty-key 503 branch (fresh process)
============================================================

Preconditions: no chatbot/houduan/.env, no DEEPSEEK_API_KEY in the process
environment, and a freshly started uvicorn process.

Startup:

    ⚠️ DEEPSEEK_API_KEY 未配置
    INFO:     Started server process [32140]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

Page after sending "空Key分支验证":

    空Key分支验证
    请求失败：后端未配置 DEEPSEEK_API_KEY：请在 chatbot/houduan/.env 中填写后重启服务。

Backend access log:

    INFO:     127.0.0.1:60541 - "OPTIONS /chat HTTP/1.1" 200 OK
    INFO:     127.0.0.1:60541 - "POST /chat HTTP/1.1" 503 Service Unavailable

There was no [upstream] line because _get_api_key() raised 503 before any
outbound request. load_dotenv(ENV_PATH) runs only at module import time, so
changing .env requires restarting uvicorn; otherwise the old process may still
hold the previous key.

============================================================
K. Method A (file://) page acceptance (manual)
============================================================

The automated browser environment blocks the file:// protocol, so no automated
file:// page result is claimed in this file.

Manual steps:

    1. Start the backend with a real DEEPSEEK_API_KEY.
    2. Double-click chatbot/qinduan/index.html so the address bar is
       file:///.../chatbot/qinduan/index.html.
    3. Send "请用一句话介绍你自己".

Expected result:

    - The page shows the question and a bot reply.
    - DevTools Network shows POST /chat with HTTP 200.
    - Response headers include access-control-allow-origin: *.
    - Console has no CORS error.

Status: manual acceptance step, not an automated result. Method B in section H
is a verified page-success run but does not replace this file:// browser check.

```
