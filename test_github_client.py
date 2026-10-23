"""Tests for GitHubClient response handling."""

import unittest
from unittest.mock import Mock, patch

import httpx

from github_client import GitHubClient


class GitHubClientTests(unittest.TestCase):
    def make_client(
        self,
        responses: list[httpx.Response],
    ) -> tuple[GitHubClient, Mock, list[float]]:
        sleep_calls: list[float] = []
        with patch("github_client.get_github_token", return_value="test-token"):
            client = GitHubClient(sleep_func=sleep_calls.append)

        get_mock = Mock(side_effect=responses)
        client._client.get = get_mock
        self.addCleanup(client.close)
        return client, get_mock, sleep_calls

    def test_success_returns_data(self) -> None:
        client, _, _ = self.make_client(
            [httpx.Response(200, json={"full_name": "owner/repo"})]
        )

        result = client.get("https://api.github.com/test")

        self.assertEqual(
            result,
            {
                "ok": True,
                "code": 200,
                "data": {"full_name": "owner/repo"},
            },
        )

    def test_401_returns_failure(self) -> None:
        client, _, _ = self.make_client([httpx.Response(401)])

        result = client.get("https://api.github.com/test")

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 401)
        self.assertIn("Token", result["error"])

    def test_404_returns_failure(self) -> None:
        client, _, _ = self.make_client([httpx.Response(404)])

        result = client.get("https://api.github.com/test")

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 404)
        self.assertIn("不存在", result["error"])

    def test_403_without_rate_limit_does_not_retry(self) -> None:
        client, get_mock, sleep_calls = self.make_client(
            [httpx.Response(403, headers={"X-RateLimit-Remaining": "42"})]
        )

        result = client.get("https://api.github.com/test")

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 403)
        self.assertIn("权限", result["error"])
        self.assertEqual(get_mock.call_count, 1)
        self.assertEqual(sleep_calls, [])

    def test_403_with_missing_rate_limit_header_does_not_retry(self) -> None:
        client, get_mock, sleep_calls = self.make_client([httpx.Response(403)])

        result = client.get("https://api.github.com/test")

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 403)
        self.assertEqual(get_mock.call_count, 1)
        self.assertEqual(sleep_calls, [])

    def test_rate_limited_403_retries_once_then_returns_success(self) -> None:
        client, get_mock, sleep_calls = self.make_client(
            [
                httpx.Response(
                    403,
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": "60",
                    },
                ),
                httpx.Response(200, json={"full_name": "owner/repo"}),
            ]
        )

        result = client.get("https://api.github.com/test")

        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], 200)
        self.assertEqual(get_mock.call_count, 2)
        self.assertEqual(sleep_calls, [30.0])

    def test_rate_limit_wait_falls_back_to_reset_header(self) -> None:
        client, _, sleep_calls = self.make_client(
            [
                httpx.Response(
                    403,
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": "1005",
                    },
                ),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        with patch("github_client.time.time", return_value=1000.0):
            client.get("https://api.github.com/test")

        self.assertEqual(sleep_calls, [5.0])

    def test_rate_limit_wait_uses_small_default_when_headers_missing(self) -> None:
        client, _, sleep_calls = self.make_client(
            [
                httpx.Response(
                    403,
                    headers={"X-RateLimit-Remaining": "0"},
                ),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        client.get("https://api.github.com/test")

        self.assertEqual(sleep_calls, [1.0])

    def test_second_rate_limited_403_does_not_trigger_third_request(self) -> None:
        headers = {
            "X-RateLimit-Remaining": "0",
            "Retry-After": "1",
        }
        client, get_mock, sleep_calls = self.make_client(
            [
                httpx.Response(403, headers=headers),
                httpx.Response(403, headers=headers),
            ]
        )

        result = client.get("https://api.github.com/test")

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 403)
        self.assertIn("仍然限流", result["error"])
        self.assertEqual(get_mock.call_count, 2)
        self.assertEqual(sleep_calls, [1.0])


if __name__ == "__main__":
    unittest.main()
