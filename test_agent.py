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
        self.assertEqual(create.call_count, agent.MAX_STEPS)
        self.assertEqual(trace["steps"][-1]["exit_loop"], True)


if __name__ == "__main__":
    unittest.main()
