"""Tests for the Agent loop safety brake."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import agent


class DummyMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, **_kwargs):
        payload = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ]
        return {key: value for key, value in payload.items() if value is not None}


class AgentLoopTests(unittest.TestCase):
    def test_completed_loop_generates_markdown_report(self) -> None:
        tool_call = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(
                name="get_file_content",
                arguments=(
                    '{"owner":"owner","repo":"repo","path":"file.py"}'
                ),
            ),
        )
        responses = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(message=DummyMessage(None, [tool_call]))
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(message=DummyMessage("初步回答"))
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=DummyMessage(
                            "## 任务概述\n概述\n"
                            "## 执行过程\n执行 [见 trace step 1]\n"
                            "## 分析结果\n分析 [见 trace step 1]\n"
                            "## 结论\n结论 [见 trace step 1]"
                        )
                    )
                ]
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "agent_trace.json"
            report_path = Path(temp_dir) / "report.md"
            with (
                patch.object(agent, "TRACE_PATH", trace_path),
                patch.object(agent, "REPORT_PATH", report_path),
                patch.object(
                    agent,
                    "EVIDENCE_DIR",
                    Path(temp_dir) / "evidence",
                ),
                patch("agent.OpenAI") as openai_cls,
                patch(
                    "agent.execute_tool",
                    return_value={
                        "ok": True,
                        "code": 200,
                        "result": {
                            "path": "file.py",
                            "content": "print('evidence')\n",
                            "total_lines": 1,
                            "truncated": False,
                            "empty": False,
                        },
                    },
                ),
            ):
                create = openai_cls.return_value.chat.completions.create
                create.side_effect = responses
                report = agent.run_agent(
                    "analyze",
                    "test-key",
                    trace_enabled=True,
                )

            report_text = report_path.read_text(encoding="utf-8")
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            evidence_path = Path(temp_dir) / trace["evidence_files"][0]
            evidence_text = evidence_path.read_text(encoding="utf-8")

        self.assertTrue(report_text.startswith("## 任务概述"))
        self.assertEqual(report, report_text)
        self.assertEqual(create.call_count, 3)
        report_messages = create.call_args_list[2].kwargs["messages"]
        self.assertEqual(report_messages[-2]["content"], "初步回答")
        self.assertIn("## 任务概述", report_messages[-1]["content"])
        self.assertIn("[见 trace step N]", report_messages[-1]["content"])
        self.assertIn("- step 1:", report_messages[-1]["content"])
        self.assertIn("httpx2", report_messages[-1]["content"])
        self.assertIn("evidence/owner_repo_file.py.txt", report_messages[-1]["content"])
        self.assertNotIn("tools", create.call_args_list[2].kwargs)
        self.assertEqual(trace["stop_reason"], "completed")
        self.assertEqual(trace["actual_steps"], 1)
        self.assertEqual(trace["max_steps"], agent.MAX_STEPS)
        self.assertEqual(evidence_text, "print('evidence')\n")

    def test_max_steps_returns_safely_and_records_reason(self) -> None:
        responses = []
        for number in range(agent.MAX_STEPS):
            call = SimpleNamespace(
                id=f"call_{number}",
                function=SimpleNamespace(
                    name="get_current_time",
                    arguments="{}",
                ),
            )
            responses.append(
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(message=DummyMessage(None, [call]))
                    ]
                )
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "agent_trace.json"
            with (
                patch.object(agent, "TRACE_PATH", trace_path),
                patch("agent.OpenAI") as openai_cls,
                patch(
                    "agent.execute_tool",
                    return_value={"ok": True, "result": {"value": "ok"}},
                ),
            ):
                create = openai_cls.return_value.chat.completions.create
                create.side_effect = responses
                answer = agent.run_agent(
                    "keep going",
                    "test-key",
                    trace_enabled=True,
                )

            trace = json.loads(trace_path.read_text(encoding="utf-8"))

        self.assertEqual(answer, f"达到最大步数 {agent.MAX_STEPS}，未能得到最终回答。")
        self.assertEqual(trace["stop_reason"], "max_steps_reached")
        self.assertEqual(trace["max_steps"], agent.MAX_STEPS)
        self.assertEqual(trace["actual_steps"], agent.MAX_STEPS)
        self.assertEqual(create.call_count, agent.MAX_STEPS)
        self.assertEqual(trace["steps"][-1]["exit_loop"], True)


if __name__ == "__main__":
    unittest.main()
