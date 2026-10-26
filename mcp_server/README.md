# MCP Demo Server

Install the official `mcp` package in a local virtual environment, then start
the stdio server:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install "mcp==2.3.0"
python server.py
```

The process prints no startup banner. It is running normally while it waits
silently for JSON-RPC messages over stdio.
