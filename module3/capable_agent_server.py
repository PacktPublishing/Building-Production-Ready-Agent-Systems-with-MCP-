"""Capable Agent as MCP Server -- Module 3, Deliverable 2.

An Opus 4.6 agent connected to the meta-tools MCP server, exposed as
an MCP server itself via as_mcp_server().  Other agents (including
small local models) can call this agent through MCP as if it were just
another tool.
"""

import anyio
from agent_framework import Agent, MCPStdioTool
from agent_framework.anthropic import AnthropicClient
from dotenv import load_dotenv

load_dotenv()

# === MCP CONNECTION: meta-tools server ========================================
madeuptasks_meta = MCPStdioTool(
    name="madeuptasks-meta",
    command="python3",
    args=["-m", "madeuptasks_mcp_meta"],
    env={
        "MADEUPTASKS_API_URL": "http://localhost:8090/api/v1",
        "MADEUPTASKS_API_TOKEN": "tf_token_alice",
    },
    approval_mode="never_require",
)

# === MODEL ====================================================================
client = AnthropicClient(model_id="claude-opus-4-6")

# === AGENT ====================================================================
EXPERT_INSTRUCTION = """\
You are an expert project management assistant with deep knowledge of the
MadeUpTasks platform API.  Your responses will be consumed by another AI agent,
not directly by a human.

Guidelines:
- Be precise and structured.  Return data in a clear, parseable format.
- Always use the available tools to retrieve real data -- never fabricate.
- When navigating the API, start with list_endpoints to discover available
  resources, then describe_endpoint to understand parameters, then
  execute_endpoint to fetch data.
- For multi-step requests, complete all steps before responding.
- Include relevant IDs alongside names so the calling agent can take action.
- If a request is ambiguous, make a reasonable interpretation and note your
  assumption in the response.
- Keep responses concise -- no conversational filler.
"""

agent = Agent(
    client=client,
    name="MadeUpTasksExpert",
    description=(
        "Expert project management assistant that can navigate the MadeUpTasks "
        "API to answer complex questions and perform multi-step workflows"
    ),
    instructions=EXPERT_INSTRUCTION,
    tools=madeuptasks_meta,
)

# === EXPOSE AS MCP SERVER =====================================================

async def run():
    server = agent.as_mcp_server()
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    anyio.run(run)
