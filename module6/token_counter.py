#!/usr/bin/env python3
"""Token Counter — Module 6.

Connects to one or more MCP servers, lists their tools, and measures the token
cost of tool definitions.  Shows exactly what the model "sees" before a single
tool call is made — and how that cost multiplies across a conversation.

This is the kind of tool that surprisingly few developers use, but it makes
the cost of verbose tool descriptions immediately visible.

Usage:
    # Compare baseline vs logical servers (both must be reachable via stdio)
    python token_counter.py

    # With custom API URL
    MADEUPTASKS_API_URL=http://localhost:8090/api/v1 python token_counter.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

# A rough but useful heuristic: ~4 characters per token for English text
# and JSON schemas.  For precise counts, use tiktoken or the Anthropic
# tokenizer — but 4 chars/token is close enough for cost awareness.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token estimate.  Good enough for relative comparisons."""
    return max(1, len(text) // CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Tool definition measurement
# ---------------------------------------------------------------------------

@dataclass
class ToolMeasurement:
    name: str
    description_tokens: int
    schema_tokens: int
    total_tokens: int
    raw_description: str
    raw_schema: str


async def measure_server(
    name: str,
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
) -> list[ToolMeasurement]:
    """Connect to an MCP server, list tools, and measure each definition."""
    params = StdioServerParameters(command=command, args=args, env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

            measurements: list[ToolMeasurement] = []
            for tool in result.tools:
                desc = tool.description or ""
                schema_str = json.dumps(tool.inputSchema, indent=2) if tool.inputSchema else "{}"
                desc_tokens = estimate_tokens(desc)
                schema_tokens = estimate_tokens(schema_str)

                measurements.append(ToolMeasurement(
                    name=tool.name,
                    description_tokens=desc_tokens,
                    schema_tokens=schema_tokens,
                    total_tokens=desc_tokens + schema_tokens,
                    raw_description=desc,
                    raw_schema=schema_str,
                ))

            return measurements


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

SEP = "=" * 80
THIN = "-" * 80


def print_server_report(server_name: str, tools: list[ToolMeasurement]) -> int:
    """Print tool-by-tool token breakdown.  Returns total tokens."""
    print(f"\n{SEP}")
    print(f"  {server_name}")
    print(f"  {len(tools)} tool(s)")
    print(SEP)

    print(f"\n  {'Tool':<30} {'Desc':>8} {'Schema':>8} {'Total':>8}")
    print(f"  {THIN[:30]} {THIN[:8]} {THIN[:8]} {THIN[:8]}")

    grand_total = 0
    for t in sorted(tools, key=lambda x: -x.total_tokens):
        print(f"  {t.name:<30} {t.description_tokens:>8} {t.schema_tokens:>8} {t.total_tokens:>8}")
        grand_total += t.total_tokens

    print(f"  {THIN[:30]} {THIN[:8]} {THIN[:8]} {THIN[:8]}")
    print(f"  {'TOTAL':<30} {'':>8} {'':>8} {grand_total:>8}")

    return grand_total


def print_conversation_impact(server_name: str, tokens_per_msg: int, turns: int = 5) -> None:
    """Show how tool definition overhead accumulates across a conversation."""
    total = tokens_per_msg * turns  # Tool defs are sent every turn
    print(f"\n  Conversation impact ({server_name}, {turns} turns):")
    print(f"    Tool definitions per message:  {tokens_per_msg:>8,} tokens")
    print(f"    Over {turns} turns:                  {total:>8,} tokens")

    # Dollar cost
    models = [
        ("claude-opus-4-6",   15.00),
        ("claude-sonnet-4-6",  3.00),
        ("claude-haiku-4-5",   0.80),
    ]
    for model, rate in models:
        cost = total * rate / 1_000_000
        print(f"    = ${cost:.4f} just for tool defs ({model})")


def print_comparison(servers: dict[str, list[ToolMeasurement]]) -> None:
    """Side-by-side comparison of multiple servers."""
    if len(servers) < 2:
        return

    print(f"\n{SEP}")
    print("  Server Comparison")
    print(SEP)

    print(f"\n  {'Server':<30} {'Tools':>6} {'Tokens':>8} {'Per Tool':>10}")
    print(f"  {THIN[:30]} {THIN[:6]} {THIN[:8]} {THIN[:10]}")

    totals = {}
    for name, tools in servers.items():
        total = sum(t.total_tokens for t in tools)
        per_tool = total // max(len(tools), 1)
        totals[name] = total
        print(f"  {name:<30} {len(tools):>6} {total:>8,} {per_tool:>10,}")

    # Show savings relative to largest
    if totals:
        largest_name = max(totals, key=totals.get)
        largest = totals[largest_name]
        print()
        for name, total in totals.items():
            if name != largest_name and largest > 0:
                saved = largest - total
                pct = (saved / largest) * 100
                print(f"  {name} saves {saved:,} tokens ({pct:.0f}%) vs {largest_name}")


def print_biggest_offenders(all_tools: list[tuple[str, ToolMeasurement]], top_n: int = 5) -> None:
    """Show the most expensive tool definitions across all servers."""
    print(f"\n{SEP}")
    print(f"  Top {top_n} Most Expensive Tool Definitions")
    print(SEP)

    sorted_tools = sorted(all_tools, key=lambda x: -x[1].total_tokens)[:top_n]
    print(f"\n  {'Server':<20} {'Tool':<25} {'Tokens':>8}")
    print(f"  {THIN[:20]} {THIN[:25]} {THIN[:8]}")
    for server, tool in sorted_tools:
        print(f"  {server:<20} {tool.name:<25} {tool.total_tokens:>8}")


# ---------------------------------------------------------------------------
# Server configurations
# ---------------------------------------------------------------------------

def get_server_configs() -> dict[str, dict]:
    """Define which MCP servers to measure."""
    api_url = os.environ.get("MADEUPTASKS_API_URL", "http://localhost:8090/api/v1")
    api_token = os.environ.get("MADEUPTASKS_API_TOKEN", "tf_token_alice")
    env = {"MADEUPTASKS_API_URL": api_url, "MADEUPTASKS_API_TOKEN": api_token}

    base_dir = os.path.dirname(os.path.abspath(__file__))

    return {
        "Module 1: Baseline": {
            "command": sys.executable,
            "args": [os.path.join(base_dir, "..", "module1", "baseline_server.py")],
            "env": env,
        },
        "Module 2: Logical Tools": {
            "command": sys.executable,
            "args": ["-m", "madeuptasks_mcp_logical"],
            "env": {
                **env,
                "PYTHONPATH": os.path.join(base_dir, "..", "module2", "madeuptasks-mcp-logical"),
            },
        },
        "Module 2: Meta Tools": {
            "command": sys.executable,
            "args": ["-m", "madeuptasks_mcp_meta"],
            "env": {
                **env,
                "PYTHONPATH": os.path.join(base_dir, "..", "module2", "madeuptasks-mcp-meta"),
            },
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    configs = get_server_configs()
    servers: dict[str, list[ToolMeasurement]] = {}
    all_tools: list[tuple[str, ToolMeasurement]] = []

    for name, cfg in configs.items():
        try:
            tools = await measure_server(
                name=name,
                command=cfg["command"],
                args=cfg["args"],
                env=cfg.get("env"),
            )
            servers[name] = tools
            for t in tools:
                all_tools.append((name, t))
        except Exception as e:
            print(f"\n  WARNING: Could not connect to '{name}': {e}")
            print(f"           Make sure the MadeUpTasks API is running.\n")

    if not servers:
        print("No servers could be reached. Is the MadeUpTasks API running?")
        sys.exit(1)

    # Per-server reports
    for name, tools in servers.items():
        total = print_server_report(name, tools)
        print_conversation_impact(name, total)

    # Cross-server comparison
    print_comparison(servers)
    print_biggest_offenders(all_tools)

    print(f"\n{SEP}")
    print("  Token estimates use ~4 chars/token heuristic.")
    print("  For exact counts, use tiktoken or the Anthropic tokenizer.")
    print(SEP)


if __name__ == "__main__":
    asyncio.run(main())
