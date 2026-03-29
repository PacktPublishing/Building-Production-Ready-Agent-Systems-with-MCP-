"""MadeUpTasks Agent -- Module 3, Deliverable 1.

A minimal agent using Microsoft Agent Framework that connects to a
MadeUpTasks MCP server and provides a project-management assistant via
the MAF dev UI.

Swap ONE line to change the model.  Swap ONE config block to change
the tool surface (logical vs meta-tools).
"""

from pathlib import Path
from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient
# from agent_framework.ollama import OllamaChatClient
from agent_framework.devui import serve
from dotenv import load_dotenv

MODULE2_DIR = str(Path(__file__).resolve().parent.parent / "module2")

load_dotenv()

# === MODEL PROVIDER (swap one line to change model) ===========================
client = AnthropicClient(model_id="claude-opus-4-6")
# client = OllamaChatClient(model_id="qwen2.5:1.5b")

# === MCP SERVER (swap config block to change tools) ===========================
# madeuptasks_mcp = MCPStdioTool(
#     name="madeuptasks-logical",
#     command="python3",
#     args=["-m", "madeuptasks_mcp_logical"],
#     env={
#         "PYTHONPATH": MODULE2_DIR + "/madeuptasks-mcp-logical",
#         "MADEUPTASKS_API_URL": "http://localhost:8090/api/v1",
#         "MADEUPTASKS_API_TOKEN": "tf_token_alice",
#     },
#     approval_mode="never_require",
# )

# For meta-tools alternative, uncomment the block below and comment out above:
madeuptasks_mcp = MCPStdioTool(
    name="madeuptasks-meta",
    command="python3",
    args=["-m", "madeuptasks_mcp_meta"],
    env={
        "PYTHONPATH": MODULE2_DIR + "/madeuptasks-mcp-meta",
        "MADEUPTASKS_API_URL": "http://localhost:8090/api/v1",
        "MADEUPTASKS_API_TOKEN": "tf_token_alice",
    },
    approval_mode="never_require",
)

# === SYSTEM INSTRUCTION ======================================================
SYSTEM_INSTRUCTION = open(Path(__file__).resolve().parent / "system_instruction.md").read()

# === AGENT ====================================================================
agent = Agent(
    client=client,
    name="MadeUpTasksAssistant",
    description="AI project management assistant for MadeUpTasks",
    instructions=SYSTEM_INSTRUCTION,
    tools=madeuptasks_mcp,
)

# === DEV UI ===================================================================
serve(entities=[agent], port=8088, auto_open=True, instrumentation_enabled=True)
