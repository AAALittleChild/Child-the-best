from mcp.server.mcpserver import MCPServer


app = MCPServer("demo")


@app.tool()
def add(a: int, b: int) -> int:
    """返回两个整数之和"""
    return a + b


if __name__ == "__main__":
    app.run(transport="stdio")
