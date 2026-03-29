"""Example: Agent with save-to-file middleware (OpenAI variant).

Same as example_agent.py but uses OpenAI instead of Anthropic.
Set OPENAI_API_KEY in your environment.

Usage:
    python example_agent_openai.py
"""

import os
import subprocess
import sys

from agent_framework import Agent, FunctionTool, MCPStdioTool
from agent_framework.openai import OpenAIChatClient
from agent_framework.devui import serve
from dotenv import load_dotenv

from large_result_middleware import LargeResultSaverMiddleware


def _search_file(file_path: str, pattern: str, max_results: int = 20) -> str:
    """Search a saved result file for lines matching a pattern."""
    try:
        result = subprocess.run(
            ["grep", "-in", pattern, file_path],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        if not lines:
            return f"No matches for '{pattern}' in {file_path}"
        if len(lines) > max_results:
            return "\n".join(lines[:max_results]) + f"\n... ({len(lines) - max_results} more matches)"
        return "\n".join(lines)
    except FileNotFoundError:
        return f"File not found: {file_path}"


def _read_file_section(file_path: str, start_line: int = 1, num_lines: int = 50) -> str:
    """Read a section of a saved result file."""
    try:
        with open(file_path) as f:
            lines = f.readlines()
        total = len(lines)
        selected = lines[start_line - 1 : start_line - 1 + num_lines]
        result = "".join(selected)
        remaining = total - (start_line - 1 + num_lines)
        if remaining > 0:
            result += f"\n... ({remaining} more lines)"
        return f"[Lines {start_line}-{min(start_line + num_lines - 1, total)} of {total}]\n{result}"
    except FileNotFoundError:
        return f"File not found: {file_path}"


search_file = FunctionTool(
    func=_search_file,
    name="search_file",
    description=(
        "Search a saved result file for lines matching a pattern. "
        "Use this to find specific information in large results that were "
        "saved to disk, rather than reading the entire file into context."
    ),
)

read_file_section = FunctionTool(
    func=_read_file_section,
    name="read_file_section",
    description=(
        "Read a section of a saved result file by line range. "
        "Use search_file first to find relevant line numbers, then "
        "read_file_section to get the surrounding context."
    ),
)

load_dotenv()

baseline_mcp = MCPStdioTool(
    name="madeuptasks-baseline",
    command=sys.executable,
    args=[os.path.join(os.path.dirname(__file__), "..", "..", "..", "module1", "baseline_server.py")],
    env={
        "MADEUPTASKS_API_URL": os.environ.get("MADEUPTASKS_API_URL", "http://localhost:8090/api/v1"),
        "MADEUPTASKS_API_TOKEN": os.environ.get("MADEUPTASKS_API_TOKEN", "tf_token_alice"),
    },
    approval_mode="never_require",
)

# Only change: OpenAIChatClient instead of AnthropicClient
client = OpenAIChatClient(model_id="gpt-5.4-mini")

agent_with_middleware = Agent(
    client=client,
    name="WithSaveToFile",
    description="Baseline agent with save-to-file middleware",
    instructions=(
        "You are a helpful assistant for MadeUpTasks project management. "
        "When tool results are saved to files, use the search_file and "
        "read_file_section tools to retrieve the specific information you "
        "need. Search selectively — don't read entire files."
    ),
    tools=[baseline_mcp, search_file, read_file_section],
    middleware=[
        LargeResultSaverMiddleware(
            token_threshold=500,
            output_dir=".tool_results",
            preview_chars=400,
        ),
    ],
)

agent_without_middleware = Agent(
    client=client,
    name="WithoutSaveToFile",
    description="Baseline agent without middleware (full payloads in context)",
    instructions="You are a helpful assistant for MadeUpTasks project management.",
    tools=baseline_mcp,
)

if __name__ == "__main__":
    serve(entities=[agent_with_middleware, agent_without_middleware], port=8086, auto_open=True, instrumentation_enabled=True)
