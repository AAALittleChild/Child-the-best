# rb_link_1 测试证据

## 证据类型：test

- 命令：`python -m pytest -v`
- 工作目录：`chatbot/houduan`
- 采集日期：2026-10-18（Asia/Shanghai）
- 结论：`10 passed, 1 warning in 0.58s`

本文件是自包含的内联证据，不依赖 `PYTEST_RUN.txt` 或外部引用；下面的原文与仓库根目录 `PYTEST_RUN.txt` 为同一次运行。

## 完整 pytest 原文

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
