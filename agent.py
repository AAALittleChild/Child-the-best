"""Command-line entry point for the course project."""

import argparse
import json
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
REPORT_PATH = Path(__file__).resolve().with_name("report.md")


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _trace_arguments(arguments_json: str) -> Any:
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return arguments_json
    return arguments


def _summarize_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    if not result.get("ok"):
        code = result.get("code", "unknown")
        error = str(result.get("error", "未知错误")).replace("\n", " ")
        return f"ok=false, code={code}, error={error[:160]}"

    payload = result.get("result")
    if tool_name == "get_file_content" and isinstance(payload, dict):
        path = payload.get("path", "unknown")
        if payload.get("empty"):
            return f"ok=true, 文件 {path} 为空"
        status = "已截断" if payload.get("truncated") else "未截断"
        return (
            f"ok=true, 读取 {path} 共 {payload.get('total_lines', 0)} 行, "
            f"{status}"
        )

    if tool_name == "get_repo_info" and isinstance(payload, dict):
        return (
            "ok=true, 仓库概况: "
            f"language={payload.get('language')}, "
            f"stars={payload.get('stars')}, "
            f"default_branch={payload.get('default_branch')}"
        )

    if tool_name == "get_current_time" and isinstance(payload, dict):
        return f"ok=true, 当前时间: {payload.get('iso', 'unknown')}"

    compact_payload = json.dumps(payload, ensure_ascii=False)
    return f"ok=true, result={compact_payload[:160]}"


def _format_steps_for_report(steps: list[dict[str, Any]]) -> str:
    lines = []
    for step in steps:
        arguments = json.dumps(step.get("arguments"), ensure_ascii=False)
        lines.append(
            f"- step {step['step']}: "
            f"tool={step.get('tool_name') or 'none'}; "
            f"arguments={arguments}; "
            f"result={step.get('result_summary', '')}"
        )
    return "\n".join(lines)


def _generate_report(
    client: OpenAI,
    messages: list[dict[str, Any]],
    steps: list[dict[str, Any]],
) -> str:
    report_instruction = f"""请根据完整对话和工具执行记录，整理一份 Markdown 报告。

报告必须严格包含以下四个二级标题，并保持顺序：
## 任务概述
## 执行过程
## 分析结果
## 结论

执行过程和分析结果中，凡是依据工具结果的结论，必须在句末标注对应来源，
格式为 [见 trace step N]。只能引用下面列出的步骤编号，不得虚构。

工具步骤映射：
{_format_steps_for_report(steps)}

只输出 Markdown 报告正文，不要使用外层代码围栏。"""
    report_messages = [
        *messages,
        {"role": "user", "content": report_instruction},
    ]
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=report_messages,
    )
    report = response.choices[0].message.content or ""
    if not report.strip():
        report = "# 项目分析报告\n\n模型未生成报告内容。"
    return report.strip() + "\n"


def _write_trace(trace: dict[str, Any] | None) -> None:
    if trace is None:
        return

    with TRACE_PATH.open("w", encoding="utf-8") as trace_file:
        json.dump(trace, trace_file, ensure_ascii=False, indent=2)


def run_agent(question: str, api_key: str, trace_enabled: bool = False) -> str:
    """Run the tool loop and write a Markdown report after completion."""
    client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=30.0)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    steps: list[dict[str, Any]] = []
    trace = (
        {
            "model": MODEL_NAME,
            "base_url": BASE_URL,
            "started_at": _timestamp(),
            "question": question,
            "steps": steps,
            "stop_reason": None,
        }
        if trace_enabled
        else None
    )

    try:
        for step_number in range(1, MAX_STEPS + 1):
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

            tool_calls = assistant_message.tool_calls or []
            if not tool_calls:
                messages.append(assistant_payload)
                steps.append(
                    {
                        "step": step_number,
                        "tool_name": None,
                        "arguments": None,
                        "result_summary": "无工具调用，生成最终回答并退出循环",
                        "timestamp": _timestamp(),
                        "exit_loop": True,
                    }
                )
                report = _generate_report(client, messages, steps)
                REPORT_PATH.write_text(report, encoding="utf-8")
                if trace is not None:
                    trace["stop_reason"] = "completed"
                return report

            messages.append(assistant_payload)

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                arguments = tool_call.function.arguments or "{}"

                result = execute_tool(tool_name, arguments)
                result_content = json.dumps(result, ensure_ascii=False)
                steps.append(
                    {
                        "step": step_number,
                        "tool_name": tool_name,
                        "arguments": _trace_arguments(arguments),
                        "result_summary": _summarize_tool_result(
                            tool_name,
                            result,
                        ),
                        "timestamp": _timestamp(),
                        "exit_loop": False,
                    }
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
            trace["stop_reason"] = "max_steps_reached"
            steps.append(
                {
                    "step": MAX_STEPS,
                    "tool_name": None,
                    "arguments": None,
                    "result_summary": message,
                    "timestamp": _timestamp(),
                    "exit_loop": True,
                }
            )
        return message
    except OpenAIError as exc:
        message = f"调用模型失败：{exc}"
        if trace is not None:
            trace["error"] = message
            trace["stop_reason"] = "error"
            steps.append(
                {
                    "step": len(steps) + 1,
                    "tool_name": None,
                    "arguments": None,
                    "result_summary": message[:200],
                    "timestamp": _timestamp(),
                    "exit_loop": True,
                }
            )
        return message
    finally:
        if trace is not None and trace["stop_reason"] is None:
            trace["stop_reason"] = "error"
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

    run_agent(question, api_key, trace_enabled=args.trace)
    print(f"报告已写入：{REPORT_PATH}")
    if args.trace:
        print(f"Trace 已写入：{TRACE_PATH}")


if __name__ == "__main__":
    main()
