"""Test Agent for Module 2 — Live Coding

Connects to the logical or meta MCP server (whichever you've built)
and serves it through the DevUI so you can test interactions and
see the shaped responses.

Usage:
    # Test the logical server
    python test_agent.py logical

    # Test the meta server
    python test_agent.py meta

    # Test both (two agents in the DevUI)
    python test_agent.py both

Requires:
    - MadeUpTasks API running (docker compose up -d)
    - ANTHROPIC_API_KEY set in environment
"""

import os
import sys

from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient
from agent_framework.devui import serve
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("MADEUPTASKS_API_URL", "http://localhost:8090/api/v1")
API_TOKEN = os.environ.get("MADEUPTASKS_API_TOKEN", "tf_token_alice")
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

client = AnthropicClient(model_id="claude-sonnet-4-6")

SYSTEM_PROMPT = """\
You are a helpful assistant for MadeUpTasks project management.
Use the available tools to help users with their tasks and projects.
Always resolve user names and provide clear, structured responses.
"""

# --- MCP Server connections ---

def make_logical_tool():
    return MCPStdioTool(
        name="madeuptasks-logical",
        command=sys.executable,
        args=["-m", "madeuptasks_mcp_logical"],
        env={
            "MADEUPTASKS_API_URL": API_URL,
            "MADEUPTASKS_API_TOKEN": API_TOKEN,
            "PYTHONPATH": os.path.join(MODULE_DIR, "madeuptasks-mcp-logical"),
        },
        approval_mode="never_require",
    )

def make_meta_tool():
    return MCPStdioTool(
        name="madeuptasks-meta",
        command=sys.executable,
        args=["-m", "madeuptasks_mcp_meta"],
        env={
            "MADEUPTASKS_API_URL": API_URL,
            "MADEUPTASKS_API_TOKEN": API_TOKEN,
            "PYTHONPATH": os.path.join(MODULE_DIR, "madeuptasks-mcp-meta"),
        },
        approval_mode="never_require",
    )

# --- Agents ---

def make_logical_agent():
    return Agent(
        client=client,
        name="LogicalTools",
        description="Agent using shaped logical tools",
        instructions=SYSTEM_PROMPT,
        tools=make_logical_tool(),
    )

def make_meta_agent():
    return Agent(
        client=client,
        name="MetaTools",
        description="Agent using progressive-disclosure meta tools",
        instructions=SYSTEM_PROMPT,
        tools=make_meta_tool(),
    )

# --- Main ---

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "logical"

    entities = []
    if mode in ("logical", "both"):
        entities.append(make_logical_agent())
    if mode in ("meta", "both"):
        entities.append(make_meta_agent())

    if not entities:
        print(f"Unknown mode: {mode}. Use: logical, meta, or both")
        sys.exit(1)

    print(f"Starting test agent(s): {mode}")
    print(f"API: {API_URL}")
    serve(entities=entities, port=8085, auto_open=True, instrumentation_enabled=True)
