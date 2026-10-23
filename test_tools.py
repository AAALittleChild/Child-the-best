"""Tests for GitHub-backed tools."""

import base64
import json
import unittest
from unittest.mock import MagicMock, patch

from tools import BINARY_REPLACEMENT_THRESHOLD, MAX_FILE_LINES, execute_tool


class GetFileContentTests(unittest.TestCase):
    def execute_with_raw_content(self, raw_content: bytes) -> dict:
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = {
            "ok": True,
            "code": 200,
            "data": {
                "content": base64.b64encode(raw_content).decode("ascii"),
            },
        }
        arguments = json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "path": "file.txt",
            }
        )
        with patch("github_client.GitHubClient", return_value=client):
            return execute_tool("get_file_content", arguments)

    def execute_with_content(self, content: str) -> dict:
        return self.execute_with_raw_content(content.encode("utf-8"))

    def test_not_found_returns_friendly_error(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = {
            "ok": False,
            "code": 404,
            "error": "request failed with 404",
        }
        arguments = json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "path": "missing.txt",
            }
        )

        with patch("github_client.GitHubClient", return_value=client):
            result = execute_tool("get_file_content", arguments)

        self.assertEqual(
            result,
            {
                "ok": False,
                "code": 404,
                "error": "（文件不存在）",
            },
        )

    def test_empty_file_is_identified(self) -> None:
        result = self.execute_with_content("")

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["content"], "（文件为空）")
        self.assertEqual(result["result"]["total_lines"], 0)
        self.assertFalse(result["result"]["truncated"])
        self.assertTrue(result["result"]["empty"])

    def test_exactly_max_lines_is_not_truncated(self) -> None:
        content = "\n".join(f"line {number}" for number in range(1, 201))

        result = self.execute_with_content(content)

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["content"], content)
        self.assertEqual(result["result"]["total_lines"], MAX_FILE_LINES)
        self.assertFalse(result["result"]["truncated"])
        self.assertFalse(result["result"]["empty"])

    def test_content_over_max_lines_is_truncated(self) -> None:
        lines = [f"line {number}" for number in range(1, 202)]

        result = self.execute_with_content("\n".join(lines))

        expected = (
            "\n".join(lines[:MAX_FILE_LINES])
            + "\n（已截断，仅显示前 200 行，共 201 行）"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["content"], expected)
        self.assertEqual(result["result"]["total_lines"], 201)
        self.assertTrue(result["result"]["truncated"])

    def test_binary_file_with_nul_byte_is_rejected(self) -> None:
        result = self.execute_with_raw_content(b"abc\x00def")

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 415)
        self.assertIn("二进制", result["error"])

    def test_binary_file_with_high_replacement_ratio_is_rejected(self) -> None:
        invalid_byte_count = int(1 / BINARY_REPLACEMENT_THRESHOLD) + 1
        result = self.execute_with_raw_content(b"\xff" * invalid_byte_count)

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], 415)
        self.assertIn("二进制", result["error"])


class ListFilesTests(unittest.TestCase):
    def test_list_files_returns_compact_entries(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = {
            "ok": True,
            "code": 200,
            "data": [
                {
                    "name": "src",
                    "path": "src",
                    "type": "dir",
                    "size": 0,
                    "download_url": None,
                },
                {
                    "name": "pyproject.toml",
                    "path": "pyproject.toml",
                    "type": "file",
                    "size": 12345,
                    "download_url": "https://example.invalid",
                },
            ],
        }

        with patch("github_client.GitHubClient", return_value=client):
            result = execute_tool(
                "list_files",
                '{"owner": "openai", "repo": "openai-python"}',
            )

        client.get.assert_called_once_with(
            "https://api.github.com/repos/openai/openai-python/contents"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["result"]["entries"],
            [
                {"name": "src", "path": "src", "type": "dir", "size": 0},
                {
                    "name": "pyproject.toml",
                    "path": "pyproject.toml",
                    "type": "file",
                    "size": 12345,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
