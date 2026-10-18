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
INFO:     Started server process [23620]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

端口确认：

```text
netstat -ano | findstr :8000
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       23620

Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet
True
```

访问地址：

- 后端聊天接口：`http://127.0.0.1:8000/chat`
- FastAPI 文档：`http://127.0.0.1:8000/docs`，实测返回 `200`
- 前端页面：双击 `chatbot/qinduan/index.html`，即 `file:///.../chatbot/qinduan/index.html`
- 端到端浏览器测试时，同一份页面通过 `python -m http.server 8080 --directory chatbot/qinduan` 打开为 `http://127.0.0.1:8080/index.html`；页面代码没有变化

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
[upstream] 402 {"error":{"message":"Insufficient Balance","type":"insufficient_quota"}}
```

响应体截断到 200 字符，不打印 `Authorization` 头或 API Key。写到 stderr 是为了与 uvicorn 的 INFO 日志走同一采集流，避免只抓 stderr 时漏掉上游原文。

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

当前仓库没有 `.github/workflows`，因此本次没有新增 GitHub Actions 工作流；运行证据以本文件和 `runtime-evidence.txt` 的原始输出为准。
