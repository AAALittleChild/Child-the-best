"""Command-line entry point for the course project."""

from tools import get_github_token


def main() -> None:
    """Start the CLI and print a short readiness greeting."""
    token = get_github_token()
    token_status = "已配置" if token else "未配置"

    print("你好，课程项目已就绪！")
    print(f"GitHub Token：{token_status}")


if __name__ == "__main__":
    main()
