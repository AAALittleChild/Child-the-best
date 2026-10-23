"""Tests for GitHub-backed tools."""

import base64
import json
import unittest
from unittest.mock import MagicMock, patch

from tools import MAX_FILE_LINES, execute_tool


class GetFileContentTests(unittest.TestCase):
    def execute_with_content(self, content: str) -> dict:
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = {
            "ok": True,
            "code": 200,
            "data": {
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
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

    def test_exactly_max_lines_is_not_truncated(self) -> None:
        content = "\n".join(f"line {number}" for number in range(1, 201))

        result = self.execute_with_content(content)

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["content"], content)
        self.assertEqual(result["result"]["total_lines"], MAX_FILE_LINES)
        self.assertFalse(result["result"]["truncated"])

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


if __name__ == "__main__":
    unittest.main()
