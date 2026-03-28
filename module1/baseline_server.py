"""Baseline MCP Server
"""

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("madeuptasks-baseline")

API_URL = os.environ.get("MADEUPTASKS_API_URL", "http://localhost:8090/api/v1")
API_TOKEN = os.environ.get("MADEUPTASKS_API_TOKEN", "tf_token_alice")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }


def _dump(data: object) -> str:
    """Dump the raw API response as JSON. No shaping, no filtering."""
    return json.dumps(data, indent=2, default=str)


# ── Tool 1: list_tasks ──────────────────────────────────────────────────────
# Problem: returns the full raw response — 40+ fields per task, pagination
# metadata, internal audit fields, everything. Huge context cost.


@mcp.tool()
async def list_tasks(project_id: str) -> str:
    """List all tasks in a MadeUpTasks project.

    This tool retrieves tasks from the specified project. The project_id
    parameter should be the internal project identifier (e.g. prj_001).
    Tasks are returned in creation order. The response includes full task
    objects with all fields including metadata, audit trails, webhook
    configurations, SLA tiers, compliance tags, time tracking data,
    risk scores, and other internal system fields. Pagination is cursor-
    based — if has_more is true, pass the next_cursor value to get more
    results. Default page size is 20.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_URL}/projects/{project_id}/tasks",
            headers=_headers(),
        )
    return _dump(resp.json())


# ── Tool 2: get_task ─────────────────────────────────────────────────────────
# Problem: returns the full 40+ field response. No comments included even
# though users almost always want them. No name resolution for assignee_id.


@mcp.tool()
async def get_task(task_id: str) -> str:
    """Get complete details for a single MadeUpTasks task.

    Returns the full task object including all metadata fields, audit
    trail, webhook configuration, SLA tier, compliance tags, time
    tracking, risk score, cost allocation, dependency IDs, blocking
    IDs, subtask IDs, custom fields, notification preferences, and
    data classification. The assignee_id field contains the internal
    user ID — use the users endpoint to resolve it to a name.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_URL}/tasks/{task_id}",
            headers=_headers(),
        )
    return _dump(resp.json())


# ── Tool 3: create_task ──────────────────────────────────────────────────────
# Problem: no confirmation step, no assignee name resolution (requires user
# ID, not name), no default priority, no validation.


@mcp.tool()
async def create_task(
    project_id: str,
    title: str,
    description: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
) -> str:
    """Create a new task in a MadeUpTasks project.

    Parameters:
    - project_id: The internal project identifier (e.g. prj_001)
    - title: The task title (required)
    - description: Optional description text
    - assignee_id: The internal user ID to assign to (e.g. usr_002).
      Note: this must be the user ID, not the user's name.
    - priority: One of 'low', 'medium', 'high'. If not provided, the
      API may use a default or may leave it null depending on the
      project's default_task_template configuration.
    """
    body: dict = {"title": title}
    if description:
        body["description"] = description
    if assignee_id:
        body["assignee_id"] = assignee_id
    if priority:
        body["priority"] = priority

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_URL}/projects/{project_id}/tasks",
            headers=_headers(),
            json=body,
        )
    return _dump(resp.json())


# ── Tool 4: search_tasks ─────────────────────────────────────────────────────
# Problem: returns full raw results, no status normalization, no name
# resolution for assignee filtering — requires user ID.


@mcp.tool()
async def search_tasks(
    q: str | None = None,
    status: str | None = None,
    assignee_id: str | None = None,
    project_id: str | None = None,
) -> str:
    """Search for tasks across all MadeUpTasks projects.

    Parameters:
    - q: Full-text search query matching task titles and descriptions
    - status: Filter by status. Must be exact canonical value: 'open',
      'in_progress', 'in-review', 'done', or 'blocked'. Other formats
      like 'In Progress' or 'IN_REVIEW' may or may not work depending
      on API version.
    - assignee_id: Filter by internal user ID (e.g. usr_002). Does not
      accept user names.
    - project_id: Filter by project ID (e.g. prj_001).
    """
    params: dict = {}
    if q:
        params["q"] = q
    if status:
        params["status"] = status
    if assignee_id:
        params["assignee_id"] = assignee_id
    if project_id:
        params["project_id"] = project_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_URL}/tasks/search",
            headers=_headers(),
            params=params,
        )
    return _dump(resp.json())


# ── Tool 5: update_task_status ───────────────────────────────────────────────
# Problem: no pre-validation of valid transitions, no next-step hinting,
# raw error on failure.


@mcp.tool()
async def update_task_status(task_id: str, new_status: str) -> str:
    """Change the status of a task.

    Attempts to transition the task to the given status. The new_status
    should be one of: 'open', 'in_progress', 'in-review', 'done',
    'blocked'. Not all transitions are valid — the API enforces a state
    machine but this tool does not check beforehand.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_URL}/tasks/{task_id}/transition",
            headers=_headers(),
            json={"to": new_status},
        )
    return _dump(resp.json())


# ── Tool 6: get_all_projects ──────────────────────────────────────────────────


@mcp.tool()
async def get_all_projects() -> str:
    """List all projects in MadeUpTasks.

    Returns the full list of projects the current user has access to,
    including project IDs, names, and other metadata.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_URL}/projects",
            headers=_headers(),
        )
    return _dump(resp.json())


if __name__ == "__main__":
    mcp.run(transport="stdio")
