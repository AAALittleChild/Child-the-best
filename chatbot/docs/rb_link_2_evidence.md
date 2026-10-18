# rb_link_2 运行与排查证据

- 项目：Child-the-best / chatbot
- 采集日期：2026-10-18（Asia/Shanghai）
- 环境：Windows，Python 3.14.6，uvicorn 0.40.0，FastAPI 0.143.3，httpx 0.28.1
- 原始文本证据：[runtime-evidence.txt](runtime-evidence.txt)
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

## 5. 测试与最终页面状态

```powershell
cd chatbot/houduan
python -m pytest -q
```

实际结果：

```text
........                                                                 [100%]
8 passed, 1 warning in 0.62s
```

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
