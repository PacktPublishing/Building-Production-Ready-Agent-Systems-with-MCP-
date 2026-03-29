"""Multi-Agent MadeUpTasks Assistant -- Module 3, Deliverable 3.

A Qwen 1.5B agent with two MCP connections:
  1. Logical tools -- for simple, direct operations it can handle itself.
  2. Capable agent (Opus via AsMcpServer) -- for complex queries it delegates.

This demonstrates agent-as-tool composition over MCP: the same protocol
used for tool servers also connects agents to each other.
"""

import os
from pathlib import Path
from agent_framework import Agent, MCPStdioTool
from agent_framework.ollama import OllamaChatClient
from agent_framework.devui import serve
from dotenv import load_dotenv

MODULE2_DIR = str(Path(__file__).resolve().parent.parent / "module2")

load_dotenv()

# === MCP CONNECTION 1: logical tools (direct, simple) =========================
logical_tools = MCPStdioTool(
    name="madeuptasks-logical",
    command="python3",
    args=["-m", "madeuptasks_mcp_logical"],
    env={
        "PYTHONPATH": MODULE2_DIR + "/madeuptasks-mcp-logical",
        "MADEUPTASKS_API_URL": "http://localhost:8090/api/v1",
        "MADEUPTASKS_API_TOKEN": "tf_token_alice",
    },
    approval_mode="never_require",
)

# === MCP CONNECTION 2: capable agent (Opus, via AsMcpServer) ==================
expert_agent = MCPStdioTool(
    name="madeuptasks-expert",
    command="python3",
    args=["capable_agent_server.py"],
    env={
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "MADEUPTASKS_API_URL": "http://localhost:8090/api/v1",
        "MADEUPTASKS_API_TOKEN": "tf_token_alice",
    },
    approval_mode="never_require",
)

# === MODEL ====================================================================
client = OllamaChatClient(model_id="qwen2.5:1.5b")

# === SYSTEM INSTRUCTION =======================================================
MULTI_AGENT_INSTRUCTION = """\
You are a project management assistant for the MadeUpTasks platform.

You have two kinds of tools available:

## Direct tools (use these for simple requests)
- get_project_overview -- get a project's status, team, and task breakdown
- search_tasks -- find tasks by query, status, or assignee
- get_task_details -- get full details of a specific task
- update_task_status -- change a task's status
- create_task -- create a new task in a project
- add_comment -- add a comment to a task

## Expert assistant (use for complex requests)
- The "madeuptasks-expert" tool connects you to an expert assistant that can
  handle complex, multi-step, or cross-project queries.

### When to use the expert:
- Questions that span multiple projects
- Requests requiring analysis or summarization across many tasks
- Anything you are unsure how to handle with the direct tools
- Complex searches with multiple filters or conditions

### When to use direct tools:
- Single project overviews
- Simple task lookups or status changes
- Adding a comment to a known task
- Creating a task with clear parameters

## Important rules
- Never make up task data or project information.  Always use tools.
- When a request has both simple and complex parts, use direct tools for the
  simple parts and delegate the complex parts to the expert.
- Present all results clearly and concisely to the user.
"""

# === AGENT ====================================================================
agent = Agent(
    client=client,
    name="MadeUpTasksAssistant",
    description="AI project management assistant with expert delegation",
    instructions=MULTI_AGENT_INSTRUCTION,
    tools=[logical_tools, expert_agent],
)

# === DEV UI ===================================================================
serve(entities=[agent], port=8081, auto_open=True, instrumentation_enabled=True)
