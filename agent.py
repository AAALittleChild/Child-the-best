"""Command-line entry point for the course project."""

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError

from tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    get_deepseek_api_key,
    get_github_token,
)


BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
MAX_STEPS = 5
TRACE_PATH = Path(__file__).resolve().with_name("agent_trace.json")


def _record_event(trace: dict[str, Any] | None, event: str, **data: Any) -> None:
    if trace is None:
        return

    trace["events"].append(
        {
            "sequence": len(trace["events"]) + 1,
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": event,
            **data,
        }
    )


def _write_trace(trace: dict[str, Any] | None) -> None:
    if trace is None:
        return

    TRACE_PATH.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_agent(question: str, api_key: str, trace_enabled: bool = False) -> str:
    """Run the model loop until it returns a final answer."""
    client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=30.0)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    trace = (
        {
            "model": MODEL_NAME,
            "base_url": BASE_URL,
            "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "question": question,
            "tools": TOOL_DEFINITIONS,
            "events": [],
            "final_answer": None,
        }
        if trace_enabled
        else None
    )

    try:
        for step in range(1, MAX_STEPS + 1):
            _record_event(
                trace,
                "model_request",
                step=step,
                messages=deepcopy(messages),
                tool_choice="auto",
            )

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            assistant_message = response.choices[0].message
            assistant_payload = assistant_message.model_dump(
                mode="json",
                exclude_none=True,
            )
            _record_event(
                trace,
                "model_response",
                step=step,
                message=assistant_payload,
            )

            tool_calls = assistant_message.tool_calls or []
            if not tool_calls:
                answer = assistant_message.content or "模型未返回内容。"
                if trace is not None:
                    trace["final_answer"] = answer
                return answer

            messages.append(assistant_payload)

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                arguments = tool_call.function.arguments or "{}"
                _record_event(
                    trace,
                    "tool_call",
                    step=step,
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    arguments=arguments,
                )

                result = execute_tool(tool_name, arguments)
                result_content = json.dumps(result, ensure_ascii=False)
                _record_event(
                    trace,
                    "tool_result",
                    step=step,
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    result=result,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content,
                    }
                )

        message = f"达到最大步数 {MAX_STEPS}，未能得到最终回答。"
        if trace is not None:
            trace["error"] = message
        return message
    except OpenAIError as exc:
        message = f"调用模型失败：{exc}"
        if trace is not None:
            trace["error"] = message
        return message
    finally:
        _write_trace(trace)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="最小单工具 Agent CLI")
    parser.add_argument(
        "--trace",
        action="store_true",
        help="将每一步的入参和出参写入 agent_trace.json",
    )
    return parser.parse_args()


def main() -> None:
    """Ask one question and let the model decide whether to use a tool."""
    args = parse_args()
    github_token = get_github_token()
    token_status = "已配置" if github_token else "未配置"

    print("你好，课程项目已就绪！")
    print(f"GitHub Token：{token_status}")

    question = input("你问：").strip()
    if not question:
        print("问题不能为空。")
        return

    api_key = get_deepseek_api_key()
    if not api_key:
        print("未配置 DEEPSEEK_API_KEY，请在 .env 中填写后重试。")
        return

    answer = run_agent(question, api_key, trace_enabled=args.trace)
    print(f"回答：{answer}")
    if args.trace:
        print(f"Trace 已写入：{TRACE_PATH}")


if __name__ == "__main__":
    main()
