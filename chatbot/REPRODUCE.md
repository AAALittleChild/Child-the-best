\# 本地复现步骤文档

\## 前置条件

1\. 本机已安装 Python 3.9 及以上版本

2\. 可以正常访问大模型API接口

3\. 准备好可用的 API Key



\## 步骤1：拉取/拿到项目代码

将项目文件夹 `chatbot` 放到本地，目录结构：

chatbot/

├─ main.py

├─ index.html

├─ .gitignore

└─ REPRODUCE.md



\## 步骤2：配置环境变量密钥

1\. 在 chatbot 文件夹内新建文件 `.env`

2\. 在 `.env` 写入内容：

DEEPSEEK\_API\_KEY = 在此处填入你的 key

> .env 文件已经在 .gitignore 中配置，不会上传至代码仓库



\## 步骤3：安装项目依赖

打开终端，cd 进入 chatbot 目录，执行：

```bash

pip install fastapi uvicorn httpx python-dotenv

步骤 4：启动后端服务

终端执行启动命令：

uvicorn main:app --reload --host 0.0.0.0 --port 8000

✅ 正常启动成功标志（控制台输出）：

INFO:     Started server process \[xxxx]

INFO:     Waiting for application startup.

✅ API\_KEY读取成功

INFO:     Application startup complete.

INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

步骤 5：打开前端页面进行交互

直接双击打开 index.html

在网页输入框输入消息，点击发送

前端会 POST 请求 http://127.0.0.1:8000/chat

后端调用大模型接口，返回回答展示在页面

步骤 6：排查验证（对应评审证据）

验证后端端口监听：访问 http://127.0.0.1:8000/docs 可以打开 FastAPI 接口文档

验证前端请求：浏览器按 F12 打开开发者工具 → Network，查看 /chat 请求

成功：Status 200，可看到请求体与 reply 返回内容

验证控制台标记日志：切换到 Console，查看 A/B/C 标记输出

正常连通：标记 A → 标记 B → 标记 C

后端未启动：仅标记 A，抛出 Failed to fetch 跨域 / 连接错误

CORS：后端已配置跨域中间件，本地直接打开 html 不会拦截

终止服务

在启动后端的终端按下 Ctrl + C，停止 uvicorn 服务



