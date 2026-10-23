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

    def get(self, url: str) -> Any:
        """Send an authenticated GET request and return decoded JSON."""
        response = self._client.get(url)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
