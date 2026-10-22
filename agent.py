"""Command-line entry point for the course project."""

from openai import OpenAI, OpenAIError

from tools import get_deepseek_api_key, get_github_token


BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"


def main() -> None:
    """Ask one question, call DeepSeek once, and print the answer."""
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

    client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=30.0)

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": question}],
        )
    except OpenAIError as exc:
        print(f"调用模型失败：{exc}")
        return

    answer = response.choices[0].message.content
    print(f"回答：{answer or '模型未返回内容。'}")


if __name__ == "__main__":
    main()
