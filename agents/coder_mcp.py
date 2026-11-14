#python -m agents.coder_mcp <workdir>
#tools agent can use to manipulate files

import sys

from mcp.server.mcpserver import MCPServer

from agents.tool_layer import DEFAULT_TIMEOUT, ToolLayer

SERVER_NAME = "coder_tools"


def build_server(workdir: str) -> MCPServer:
    layer = ToolLayer(workdir)
    server = MCPServer(SERVER_NAME)

    @server.tool()
    def read_file(path: str) -> str:
        return layer.read_file(path)

    @server.tool()
    def write_file(path: str, content: str) -> str:
        return layer.write_file(path, content)

    @server.tool()
    def edit_file(path: str, old_text: str, new_text: str) -> str:
        return layer.edit_file(path, old_text, new_text)

    @server.tool()
    def execute_code(code: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        return str(layer.execute_code(code, min(timeout, 120)))

    return server


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m agents.coder_mcp <workdir>")
    build_server(sys.argv[1]).run("stdio")
