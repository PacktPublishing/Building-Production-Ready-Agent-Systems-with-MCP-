"""Baseline Agent

Usage:
    python baseline_agent.py

Requires:
    - MadeUpTasks API running on localhost:8090
    - ANTHROPIC_API_KEY set in environment or .env file
"""

import os
import sys

from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient
from agent_framework.devui import serve
from dotenv import load_dotenv

load_dotenv()

# === MCP SERVER ===============================================================
# Connects to the baseline MCP server — raw API passthrough, no shaping.
baseline_mcp = MCPStdioTool(
    name="madeuptasks-baseline",
    command=sys.executable,
    args=[os.path.join(os.path.dirname(__file__), "baseline_server.py")],
    env={
        "MADEUPTASKS_API_URL": os.environ.get("MADEUPTASKS_API_URL", "http://localhost:8090/api/v1"),
        "MADEUPTASKS_API_TOKEN": os.environ.get("MADEUPTASKS_API_TOKEN", "tf_token_alice"),
    },
    approval_mode="never_require",
)

# === MODEL ====================================================================
client = AnthropicClient(model_id="claude-sonnet-4-6")

# === SYSTEM PROMPT ============================================================
# Not a lot of info...
SYSTEM_PROMPT = "You are a helpful assistant for MadeUpTasks project management."

# === AGENT ====================================================================
agent = Agent(
    client=client,
    name="MadeUpTasksBaseline",
    description="Basic MadeUpTasks assistant",
    instructions=SYSTEM_PROMPT,
    tools=baseline_mcp,
)

# === LAUNCH ===================================================================
if __name__ == "__main__":
    serve(entities=[agent], port=8084, auto_open=True, instrumentation_enabled=True)
