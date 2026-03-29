"""MadeUpTasks Meta-Tools MCP Server.

Provides four progressive-disclosure tools that let an AI agent discover,
explore, and execute any MadeUpTasks API endpoint without hard-coded business
logic in the server.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

from mcp.server.fastmcp import FastMCP

from . import api_client, manifest

mcp = FastMCP(
    "madeuptasks-meta",
    instructions=(
        "This server exposes the MadeUpTasks API through four progressive-disclosure tools.\n"
        "\n"
        "Recommended workflow:\n"
        "1. Call list_endpoints() with no arguments to see available API groups.\n"
        "2. Call list_endpoints(group=...) to see endpoints in a group.\n"
        "3. Call describe_endpoint(method, path) to get full details for one endpoint.\n"
        "4. Call execute_endpoint(method, path, ...) to call the API.\n"
        "\n"
        "You can also use search_endpoints(query) to find endpoints by keyword.\n"
        "Always call describe_endpoint before execute_endpoint so you know the\n"
        "expected parameters and request body format."
    ),
)


# ── Tool 1: list_endpoints ───────────────────────────────────────────────────


@mcp.tool()
def list_endpoints(group: str | None = None) -> str:
    """List available API endpoint groups, or list endpoints within a specific group.

    Call without arguments to see all groups with descriptions and endpoint counts.
    Provide a group name to see the endpoints in that group (method, path, summary).
    """
    if group is None:
        groups = manifest.get_groups()
        return json.dumps(groups, indent=2)

    endpoints = manifest.get_endpoints_by_group(group)
    if endpoints is None:
        available = [g["name"] for g in manifest.get_groups()]
        return json.dumps(
            {
                "error": f"Unknown group '{group}'.",
                "available_groups": available,
            },
            indent=2,
        )
    return json.dumps(endpoints, indent=2)


# ── Tool 2: search_endpoints ────────────────────────────────────────────────


@mcp.tool()
def search_endpoints(query: str) -> str:
    """Search for API endpoints by keyword.

    Performs case-insensitive substring matching across endpoint summaries,
    descriptions, tags, and parameter names.  Returns matching endpoints with
    their group, method, path, and summary.
    """
    results = manifest.search(query)
    if not results:
        return json.dumps({"message": f"No endpoints matched '{query}'.", "results": []}, indent=2)
    return json.dumps(results, indent=2)


# ── Tool 3: describe_endpoint ────────────────────────────────────────────────


@mcp.tool()
def describe_endpoint(method: str, path: str) -> str:
    """Get full details for a specific API endpoint.

    Provide the HTTP method and the template path exactly as shown by
    list_endpoints (e.g. method="GET", path="/projects/{id}").
    Returns the full description, parameters, request body schema, and
    a response example.
    """
    detail = manifest.get_detail(method, path)
    if detail is None:
        return json.dumps(
            {
                "error": f"No endpoint found for {method.upper()} {path}.",
                "hint": "Use list_endpoints() or search_endpoints() to find valid endpoints.",
            },
            indent=2,
        )
    return json.dumps(detail, indent=2)


# ── Tool 4: execute_endpoint ────────────────────────────────────────────────


@mcp.tool()
async def execute_endpoint(
    method: str,
    path: str,
    body: str | None = None,
    query: str | None = None,
) -> str:
    """Execute an API endpoint against the live MadeUpTasks API.

    Parameters
    ----------
    method : str
        HTTP method (GET, POST, PUT, DELETE).
    path : str
        The actual path with real values substituted, e.g. /projects/prj_001
        (not the template form /projects/{id}).
    body : str, optional
        JSON string for the request body (POST/PUT requests).
    query : str, optional
        Query string without leading '?', e.g. "status=open&limit=5".

    Returns the raw API response formatted as JSON.
    Use describe_endpoint first to understand the expected parameters.
    """
    # Parse optional body
    parsed_body: dict | None = None
    if body:
        try:
            parsed_body = json.loads(body)
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"Invalid JSON body: {exc}"}, indent=2)

    # Parse optional query string into params dict
    parsed_params: dict[str, str] | None = None
    if query:
        qs = parse_qs(query, keep_blank_values=False)
        # parse_qs returns lists; flatten single values
        parsed_params = {k: v[0] if len(v) == 1 else v for k, v in qs.items()}

    result = await api_client.request(
        method=method,
        path=path,
        body=parsed_body,
        params=parsed_params,
    )

    return json.dumps(result, indent=2, default=str)
