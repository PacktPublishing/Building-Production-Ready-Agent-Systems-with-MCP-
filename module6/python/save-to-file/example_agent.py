"""Example: Agent with save-to-file middleware.

Demonstrates the LargeResultSaverMiddleware by connecting to the baseline
MCP server (which returns huge raw API responses) and showing how the
middleware intercepts large results.

Usage:
    python example_agent.py

Requires:
    - MadeUpTasks API running on localhost:8090
    - ANTHROPIC_API_KEY set in environment
"""

import os
import sys

from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient
from agent_framework.devui import serve
from dotenv import load_dotenv

from large_result_middleware import LargeResultSaverMiddleware

load_dotenv()

# Use the baseline server — it returns unfiltered 40+ field responses,
# which makes the middleware's effect very visible.
baseline_mcp = MCPStdioTool(
    name="madeuptasks-baseline",
    command=sys.executable,
    args=[os.path.join(os.path.dirname(__file__), "..", "..", "module1", "baseline_server.py")],
    env={
        "MADEUPTASKS_API_URL": os.environ.get("MADEUPTASKS_API_URL", "http://localhost:8090/api/v1"),
        "MADEUPTASKS_API_TOKEN": os.environ.get("MADEUPTASKS_API_TOKEN", "tf_token_alice"),
    },
    approval_mode="never_require",
)

client = AnthropicClient(model_id="claude-sonnet-4-6")

# Create agent WITH the middleware — large results get saved to files
agent_with_middleware = Agent(
    client=client,
    name="WithSaveToFile",
    description="Baseline agent with save-to-file middleware",
    instructions=(
        "You are a helpful assistant for MadeUpTasks project management. "
        "When tool results are saved to files, mention the file path and "
        "summarize the key information from the preview."
    ),
    tools=baseline_mcp,
    middleware=[
        LargeResultSaverMiddleware(
            token_threshold=500,  # Save results over ~500 tokens
            output_dir=".tool_results",
            preview_chars=400,
        ),
    ],
)

# For comparison: same agent WITHOUT the middleware
agent_without_middleware = Agent(
    client=client,
    name="WithoutSaveToFile",
    description="Baseline agent without middleware (full payloads in context)",
    instructions="You are a helpful assistant for MadeUpTasks project management.",
    tools=baseline_mcp,
)

if __name__ == "__main__":
    # Serve both agents so participants can compare in the DevUI
    serve(entities=[agent_with_middleware, agent_without_middleware], port=8086, auto_open=True)
