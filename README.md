# 课程 Agent 项目

这是一个带工具的 DeepSeek 命令行 Agent。模型可以自主选择工具，工具结果会回传
给模型继续推理，并在任务完成后生成 `report.md`。

## 环境准备

```powershell
cd "D:\a test\agent"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填写：

```dotenv
GITHUB_TOKEN=
DEEPSEEK_API_KEY=
```

不要提交真实的 `.env`。

## 运行

```powershell
python agent.py
```

需要保存决策链时：

```powershell
python agent.py --trace
```

运行成功后会生成：

- `report.md`：带 Trace 步骤引用的 Markdown 分析报告。
- `agent_trace.json`：只记录步骤、工具、参数、结果摘要和时间戳。
- `evidence/`：文本文件工具读取到的证据片段。

## 测试

```powershell
python -m unittest discover -v
```

## 当前工具

- `get_current_time`：读取本机当前时间。
- `get_repo_info`：读取 GitHub 仓库概况。
- `list_files`：列出仓库目录中的文件和子目录。
- `get_file_content`：读取 GitHub 文本文件内容，最多返回前 200 行。
