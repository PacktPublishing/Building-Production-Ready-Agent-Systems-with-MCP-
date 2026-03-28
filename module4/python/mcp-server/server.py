"""
Module 4 - MCP Server with Scope-Gated Tools and JWT Token Validation
Wraps the project management API and demonstrates permission delegation.
Each tool requires specific OAuth scopes and forwards the user's token downstream.

Uses FastMCP's JWTVerifier to validate Keycloak-issued tokens directly.
This approach is simpler than full OAuth proxy and works with any JWT issuer.

Demo Flow:
1. Get a token from Keycloak (via curl or any OAuth client)
2. Pass the token to MCP Inspector as a bearer token
3. FastMCP validates it against Keycloak's JWKS endpoint
4. Scope-based authorization filters tools and enforces permissions
"""

import os
import logging
from typing import Optional

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_API_URL = os.getenv("PROJECT_API_URL", "http://localhost:3000")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "workshop")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger("mcp-server")

# ---------------------------------------------------------------------------
# JWT Token Validation with Keycloak
# ---------------------------------------------------------------------------

# Keycloak's JWKS endpoint (public keys for token verification)
KEYCLOAK_JWKS_URI = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

# Keycloak issuer (must match the 'iss' claim in tokens)
KEYCLOAK_ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"

# Create JWT verifier for Keycloak tokens
# This validates incoming bearer tokens against Keycloak's public keys
auth = JWTVerifier(
    jwks_uri=KEYCLOAK_JWKS_URI,
    issuer=KEYCLOAK_ISSUER,
    # audience is optional - Keycloak tokens may have 'aud' claim
    # set to your client ID if you want to enforce audience validation
    # audience="mcp-client",
)

# ---------------------------------------------------------------------------
# MCP Server with OAuth
# ---------------------------------------------------------------------------

mcp = FastMCP("MadeUpTasks Project Manager", auth=auth)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_upstream_token() -> Optional[str]:
    """
    Get the upstream OAuth token for calling downstream APIs.
    
    With JWTVerifier, the token passed by the MCP client is validated and made
    available via get_access_token(). Since we're validating Keycloak tokens
    directly (not proxying), the token is the original Keycloak JWT which
    can be forwarded to downstream APIs.
    """
    # Get the access token from FastMCP context
    token = get_access_token()
    if token is not None:
        # Log some token info for demo purposes
        logger.info("Token scopes: %s", token.scopes)
        logger.info("Token client_id: %s", token.client_id)
        return token.token
    
    # Fallback: environment variable (for manual testing without MCP client)
    env_token = os.getenv("ACCESS_TOKEN")
    if env_token:
        logger.info("Using ACCESS_TOKEN from environment (fallback)")
        return env_token
    
    return None


async def _api_request(
    method: str,
    path: str,
    token: str,
    json_body: dict | None = None,
) -> dict | list:
    """Make an authenticated request to the project API."""
    url = f"{PROJECT_API_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    logger.info("API request: %s %s", method, url)

    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=headers, json=json_body)

    if response.status_code == 401:
        logger.warning("API returned 401 - token may be invalid or expired")
        return {"error": "Authentication failed. Your token may be invalid or expired. Please re-authenticate."}

    if response.status_code == 403:
        detail = response.json().get("detail", "Insufficient permissions")
        logger.warning("API returned 403: %s", detail)
        return {"error": f"Permission denied: {detail}"}

    if response.status_code == 404:
        detail = response.json().get("detail", "Not found")
        return {"error": detail}

    response.raise_for_status()
    return response.json()


def _format_task(task: dict) -> str:
    """Format a single task for display."""
    return (
        f"[{task['id']}] {task['title']}\n"
        f"  Assignee: {task.get('assignee', 'unassigned')}\n"
        f"  Status:   {task.get('status', 'unknown')}\n"
        f"  Priority: {task.get('priority', 'unknown')}"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(auth=require_scopes("tasks:read"))
async def list_tasks() -> str:
    """
    List all tasks in the project.
    """
    token = _get_upstream_token()
    if not token:
        return (
            "Error: No access token available. "
            "Please authenticate via the MCP OAuth flow first."
        )

    logger.info("Tool: list_tasks")
    result = await _api_request("GET", "/tasks", token)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    if not result:
        return "No tasks found."

    lines = [f"Found {len(result)} task(s):\n"]
    for task in result:
        lines.append(_format_task(task))
        lines.append("")
    return "\n".join(lines)


@mcp.tool(auth=require_scopes("tasks:read"))
async def get_task(task_id: str) -> str:
    """
    Get details of a specific task.

    Args:
        task_id: The task identifier (e.g. TASK-001)
    """
    token = _get_upstream_token()
    if not token:
        return (
            "Error: No access token available. "
            "Please authenticate via the MCP OAuth flow first."
        )

    logger.info("Tool: get_task(%s)", task_id)
    result = await _api_request("GET", f"/tasks/{task_id}", token)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    return _format_task(result)


@mcp.tool(auth=require_scopes("tasks:admin"))
async def create_task(
    title: str,
    assignee: Optional[str] = None,
    priority: Optional[str] = "medium",
) -> str:
    """
    Create a new task in the project.

    Args:
        title: The task title
        assignee: Who the task is assigned to (optional)
        priority: Task priority - low, medium, high, critical (default: medium)
    """
    token = _get_upstream_token()
    if not token:
        return (
            "Error: No access token available. "
            "Please authenticate via the MCP OAuth flow first."
        )

    logger.info("Tool: create_task(title=%s)", title)
    body = {"title": title}
    if assignee:
        body["assignee"] = assignee
    if priority:
        body["priority"] = priority

    result = await _api_request("POST", "/tasks", token, json_body=body)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    return f"Task created successfully:\n\n{_format_task(result)}"


@mcp.tool(auth=require_scopes("tasks:admin"))
async def close_task(task_id: str) -> str:
    """
    Close a completed task.

    Args:
        task_id: The task identifier to close (e.g. TASK-003)
    """
    token = _get_upstream_token()
    if not token:
        return (
            "Error: No access token available. "
            "Please authenticate via the MCP OAuth flow first."
        )

    logger.info("Tool: close_task(%s)", task_id)
    result = await _api_request("PATCH", f"/tasks/{task_id}/close", token)

    if isinstance(result, dict) and "error" in result:
        return f"Error: {result['error']}"

    return f"Task closed successfully:\n\n{_format_task(result)}"


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting MCP Server: MadeUpTasks Project Manager")
    logger.info("Project API URL: %s", PROJECT_API_URL)
    logger.info("")
    logger.info("JWT Verification Configuration:")
    logger.info("  JWKS URI: %s", KEYCLOAK_JWKS_URI)
    logger.info("  Issuer:   %s", KEYCLOAK_ISSUER)
    logger.info("")
    logger.info("To use this server:")
    logger.info("  1. Get a token from Keycloak (see CHEATSHEET.md)")
    logger.info("  2. In MCP Inspector, connect to http://localhost:%d", MCP_SERVER_PORT)
    logger.info("  3. Enter the token in the 'Bearer Token' field")
    logger.info("  4. Tools will be filtered based on your token's scopes")
    logger.info("")
    
    # Run as HTTP server for bearer token authentication
    mcp.run(transport="http", port=MCP_SERVER_PORT)
