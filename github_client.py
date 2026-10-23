"""HTTP client for GitHub API requests."""

import time
from typing import Any, Callable

import httpx

from tools import get_github_token


DEFAULT_RETRY_WAIT_SECONDS = 1.0
MAX_RETRY_WAIT_SECONDS = 30.0


class GitHubClient:
    """Send authenticated requests to the GitHub API."""

    def __init__(
        self,
        timeout: float = 30.0,
        *,
        sleep_func: Callable[[float], None] = time.sleep,
        max_retry_wait: float = MAX_RETRY_WAIT_SECONDS,
    ) -> None:
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
        self._sleep = sleep_func
        self._max_retry_wait = max(0.0, max_retry_wait)

    def get(self, url: str) -> dict[str, Any]:
        """Return a structured result, retrying a rate-limited 403 once."""
        for attempt in range(2):
            response = self._client.get(url)
            status_code = response.status_code

            if status_code == 403 and self._is_rate_limited(response):
                if attempt == 0:
                    self._sleep(self._retry_wait(response))
                    continue

                return {
                    "ok": False,
                    "code": status_code,
                    "error": "GitHub API 重试后仍然限流，请稍后再试。",
                }

            if status_code == 403:
                return {
                    "ok": False,
                    "code": status_code,
                    "error": (
                        "GitHub 拒绝访问：Token 权限不足、仓库无访问权限，"
                        "或尚未完成 SSO 授权。"
                    ),
                }

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

        return {
            "ok": False,
            "code": 403,
            "error": "GitHub API 请求失败，请稍后再试。",
        }

    @staticmethod
    def _is_rate_limited(response: httpx.Response) -> bool:
        """Return whether a 403 response is a rate-limit response."""
        return response.headers.get("X-RateLimit-Remaining") == "0"

    def _retry_wait(self, response: httpx.Response) -> float:
        """Choose a bounded wait from GitHub rate-limit headers."""
        wait_seconds = self._parse_seconds(response.headers.get("Retry-After"))

        if wait_seconds is None:
            reset_at = self._parse_seconds(
                response.headers.get("X-RateLimit-Reset")
            )
            if reset_at is not None:
                wait_seconds = max(0.0, reset_at - time.time())

        if wait_seconds is None:
            wait_seconds = DEFAULT_RETRY_WAIT_SECONDS

        return min(max(0.0, wait_seconds), self._max_retry_wait)

    @staticmethod
    def _parse_seconds(value: str | None) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
