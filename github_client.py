"""HTTP client for GitHub API requests."""

from typing import Any

import httpx

from tools import get_github_token


class GitHubClient:
    """Send authenticated requests to the GitHub API."""

    def __init__(self, timeout: float = 30.0) -> None:
        token = get_github_token()
        if not token:
            raise RuntimeError("未配置 GITHUB_TOKEN，请在 .env 中填写后重试。")

        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    def get(self, url: str) -> dict[str, Any]:
        """Return a structured success or failure result."""
        response = self._client.get(url)
        status_code = response.status_code

        if status_code == 401:
            return {
                "ok": False,
                "code": status_code,
                "error": "Token 无效或已过期，请重新生成。",
            }

        if status_code == 404:
            return {
                "ok": False,
                "code": status_code,
                "error": "请求的 GitHub 资源不存在，或当前 Token 无权访问。",
            }

        if 200 <= status_code < 300:
            return {
                "ok": True,
                "code": status_code,
                "data": response.json(),
            }

        return {
            "ok": False,
            "code": status_code,
            "error": f"GitHub 请求失败（HTTP {status_code}）。",
        }

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
