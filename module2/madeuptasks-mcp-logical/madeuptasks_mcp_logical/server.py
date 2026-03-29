"""MadeUpTasks Logical Tools MCP Server.

Six tools wrapping the MadeUpTasks REST API with response shaping,
status normalization, and user-name resolution.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from .api_client import MadeUpTasksAPIError, MadeUpTasksClient
from .helpers import VALID_TRANSITIONS, normalize_status, resolve_user_name

mcp = FastMCP("madeuptasks-logical")

_client: MadeUpTasksClient | None = None


def _get_client() -> MadeUpTasksClient:
    global _client
    if _client is None:
        _client = MadeUpTasksClient()
    return _client


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def _word_overlap_score(query: str, text: str) -> float:
    """Simple word-overlap similarity between query and text.

    Returns a score between 0 and 1 based on what fraction of query words
    appear in the text.  Good enough for surfacing near-misses to a model
    that can judge relevance for itself.
    """
    if not query or not text:
        return 0.0
    q_words = set(query.lower().split())
    t_words = set(text.lower().split())
    if not q_words:
        return 0.0
    return len(q_words & t_words) / len(q_words)


def _is_overdue(due_date: str | None) -> bool:
    if not due_date:
        return False
    try:
        dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
        return dt.date() < datetime.now(timezone.utc).date()
    except (ValueError, TypeError):
        return False


async def _fetch_all_project_tasks(client: MadeUpTasksClient, project_id: str) -> list[dict]:
    """Fetch every task in a project, following cursor pagination."""
    tasks: list[dict] = []
    cursor: str | None = None

    while True:
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        raw = await client.get_raw(f"/projects/{project_id}/tasks", params=params)
        items = raw.get("data", [])
        tasks.extend(items)
        pagination = raw.get("pagination", {})
        if not pagination.get("has_more"):
            break
        cursor = pagination.get("next_cursor")
        if not cursor:
            break

    return tasks


async def _resolve_assignee_name(client: MadeUpTasksClient, assignee_id: str | None) -> str:
    """Look up a user name from their ID."""
    if not assignee_id:
        return "Unassigned"
    try:
        user = await client.get(f"/users/{assignee_id}")
        return user.get("name", assignee_id)
    except MadeUpTasksAPIError:
        return assignee_id


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 0: list_projects
# ═══════════════════════════════════════════════════════════════════════════════


# @mcp.tool()
# async def list_projects() -> str:
#     """List all projects the current user has access to.

#     Returns each project's ID, name, status, and owner. Use the project ID
#     with other tools like get_project_overview or create_task.
#     """
#     client = _get_client()

#     try:
#         projects = await client.get("/projects")
#     except MadeUpTasksAPIError as exc:
#         return _json({"error": str(exc)})

#     items = projects if isinstance(projects, list) else []
#     results = []
#     for p in items:
#         results.append({
#             "id": p.get("id"),
#             "name": p.get("name"),
#             "status": p.get("status"),
#             "description": p.get("description"),
#         })

#     return _json({"projects": results, "count": len(results)})


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 0: list_projects
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def list_projects() -> str:
    """List all projects the current user has access to.

    Returns each project's ID, name, status, and owner. Use the project ID
    with other tools like get_project_overview or create_task.
    """
    client = _get_client()

    try:
        projects = await client.get("/projects")
    except MadeUpTasksAPIError as exc:
        return _json({"error": str(exc)})

    items = projects if isinstance(projects, list) else []
    results = []
    for p in items:
        results.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "status": p.get("status"),
            "description": p.get("description"),
        })

    return _json({"projects": results, "count": len(results)})


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 1: get_project_overview
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def get_project_overview(project_id: str) -> str:
    """Get a complete overview of a project including its members and task summary.

    Returns project details, team members with roles, and a breakdown of tasks
    by status with lists of blocked and overdue tasks.
    """
    client = _get_client()

    try:
        project, members, tasks = await asyncio.gather(
            client.get(f"/projects/{project_id}"),
            client.get(f"/projects/{project_id}/members"),
            _fetch_all_project_tasks(client, project_id),
        )
    except MadeUpTasksAPIError as exc:
        return _json({"error": str(exc)})

    # Resolve owner name
    owner_name = await _resolve_assignee_name(client, project.get("owner_id"))

    # Count tasks by status, collect blocked and overdue
    status_counts: dict[str, int] = {}
    blocked_tasks: list[dict] = []
    overdue_tasks: list[dict] = []

    for t in tasks:
        st = t.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

        assignee_name = None
        for m in members:
            if m.get("user_id") == t.get("assignee_id"):
                assignee_name = m.get("name")
                break

        if st == "blocked":
            blocked_tasks.append({
                "title": t.get("title"),
                "assignee": assignee_name or "Unassigned",
            })

        if st != "done" and _is_overdue(t.get("due_date")):
            overdue_tasks.append({
                "title": t.get("title"),
                "due_date": t.get("due_date"),
                "assignee": assignee_name or "Unassigned",
            })

    result = {
        "project": {
            "name": project.get("name"),
            "description": project.get("description"),
            "status": project.get("status"),
            "owner": owner_name,
        },
        "members": [
            {"name": m.get("name"), "role": m.get("role")}
            for m in members
        ],
        "task_summary": {
            "total": len(tasks),
            "by_status": status_counts,
        },
        "blocked_tasks": blocked_tasks,
        "overdue_tasks": overdue_tasks,
    }
    return _json(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: search_tasks
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def search_tasks(
    query: str | None = None,
    project_id: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    limit: int = 10,
) -> str:
    """Search for tasks across all projects. Returns matching tasks with key fields only.

    Assignee can be a name (e.g. "Bob") or user ID. Status accepts any format
    (e.g. "in progress", "In_Progress", "wip").

    When the exact search returns no results but a text query was provided,
    returns the closest partial matches so the model can judge whether any
    are relevant to the user's intent.
    """
    client = _get_client()

    try:
        params: dict[str, Any] = {"per_page": min(limit, 50)}

        if query:
            params["q"] = query
        if project_id:
            params["project_id"] = project_id
        if status:
            params["status"] = normalize_status(status)
        if assignee:
            params["assignee_id"] = await resolve_user_name(client, assignee)

        data = await client.get("/tasks/search", params=params)
    except (MadeUpTasksAPIError, ValueError) as exc:
        return _json({"error": str(exc)})

    items = data if isinstance(data, list) else []

    # Resolve assignee names for display
    user_cache: dict[str, str] = {}

    async def get_name(uid: str | None) -> str:
        if not uid:
            return "Unassigned"
        if uid not in user_cache:
            user_cache[uid] = await _resolve_assignee_name(client, uid)
        return user_cache[uid]

    async def _shape_task(t: dict) -> dict:
        return {
            "id": t.get("id"),
            "title": t.get("title"),
            "status": t.get("status"),
            "assignee": await get_name(t.get("assignee_id")),
            "project_id": t.get("project_id"),
            "priority": t.get("priority"),
            "due_date": t.get("due_date"),
        }

    results = [await _shape_task(t) for t in items]

    # ── Fuzzy near-miss matching ──────────────────────────────────────────
    # When the API returns nothing and we have a text query, fetch all tasks
    # and surface the closest matches by word overlap.  The model can decide
    # whether any of these are what the user actually meant.
    near_misses: list[dict] | None = None
    if not items and query:
        try:
            all_params: dict[str, Any] = {"per_page": 100}
            if project_id:
                all_params["project_id"] = project_id
            all_data = await client.get("/tasks/search", params=all_params)
            all_tasks = all_data if isinstance(all_data, list) else []
        except MadeUpTasksAPIError:
            all_tasks = []

        scored: list[tuple[float, dict]] = []
        for t in all_tasks:
            title = t.get("title", "")
            desc = t.get("description", "") or ""
            score = max(
                _word_overlap_score(query, title),
                _word_overlap_score(query, desc) * 0.7,
            )
            if score > 0:
                scored.append((score, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:5]
        if top:
            near_misses = []
            for score, t in top:
                shaped = await _shape_task(t)
                shaped["match_quality"] = (
                    "high" if score >= 0.6
                    else "medium" if score >= 0.3
                    else "low"
                )
                near_misses.append(shaped)

    response: dict[str, Any] = {"tasks": results, "count": len(results)}
    if near_misses is not None:
        response["no_exact_matches"] = True
        response["nearest_tasks"] = near_misses
    return _json(response)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 3: get_task_details
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def get_task_details(task_id: str) -> str:
    """Get full details of a specific task including its recent comments.

    Returns essential task fields and the latest 5 comments with author names.
    """
    client = _get_client()

    try:
        task, comments = await asyncio.gather(
            client.get(f"/tasks/{task_id}"),
            client.get(f"/tasks/{task_id}/comments", params={"limit": 5}),
        )
    except MadeUpTasksAPIError as exc:
        return _json({"error": str(exc)})

    assignee_name = await _resolve_assignee_name(client, task.get("assignee_id"))

    # Resolve comment authors
    author_cache: dict[str, str] = {}

    async def get_author(uid: str) -> str:
        if uid not in author_cache:
            author_cache[uid] = await _resolve_assignee_name(client, uid)
        return author_cache[uid]

    shaped_comments = []
    comment_list = comments if isinstance(comments, list) else []
    for c in comment_list[:5]:
        shaped_comments.append({
            "author": await get_author(c.get("author_id", "")),
            "timestamp": c.get("created_at"),
            "body": (c.get("body") or "")[:500],
        })

    result = {
        "task": {
            "id": task.get("id"),
            "title": task.get("title"),
            "description": task.get("description"),
            "status": task.get("status"),
            "priority": task.get("priority"),
            "assignee": assignee_name,
            "due_date": task.get("due_date"),
            "labels": task.get("labels", []),
            "created_at": task.get("created_at"),
        },
        "recent_comments": shaped_comments,
    }
    return _json(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 4: update_task_status
# ═══════════════════════════════════════════════════════════════════════════════


def _find_status_path(from_status: str, to_status: str) -> list[str] | None:
    """BFS through the state machine to find the shortest transition path."""
    if from_status == to_status:
        return [from_status]
    queue: deque[list[str]] = deque([[from_status]])
    visited: set[str] = {from_status}
    while queue:
        path = queue.popleft()
        for next_status in VALID_TRANSITIONS.get(path[-1], []):
            if next_status in visited:
                continue
            new_path = path + [next_status]
            if next_status == to_status:
                return new_path
            visited.add(next_status)
            queue.append(new_path)
    return None


@mcp.tool()
async def update_task_status(task_id: str, new_status: str) -> str:
    """Change the status of a task. Validates the transition is allowed.

    Accepts any status format (e.g. "in progress", "IN_REVIEW"). Returns
    the previous status, new status, and available next transitions.

    If the transition is not directly allowed, suggests the shortest
    multi-step path through the state machine.

    On success, includes contextual hints about the task's current state
    (e.g. overdue, unassigned) that may be worth mentioning to the user.
    """
    client = _get_client()

    try:
        new_status = normalize_status(new_status)
    except ValueError as exc:
        return _json({"error": str(exc)})

    # Fetch the task first so we can provide context regardless of outcome
    try:
        task = await client.get(f"/tasks/{task_id}")
    except MadeUpTasksAPIError as exc:
        return _json({"error": str(exc)})

    current_status = task.get("status", "")

    # Check if this transition is directly valid
    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        # Transition not allowed — help the model find the right path
        path = _find_status_path(current_status, new_status)
        result: dict[str, Any] = {
            "error": f"Cannot transition directly from '{current_status}' to '{new_status}'.",
            "current_status": current_status,
            "allowed_transitions_from_current": VALID_TRANSITIONS.get(current_status, []),
        }
        if path and len(path) > 2:
            result["suggested_path"] = path
            result["next_step"] = path[1]
            result["hint"] = (
                f"To reach '{new_status}', transition through: "
                + " → ".join(path)
                + f". Call update_task_status with '{path[1]}' as the next step."
            )
        elif path is None:
            result["hint"] = f"There is no valid path from '{current_status}' to '{new_status}'."
        return _json(result)

    try:
        data = await client.post(
            f"/tasks/{task_id}/transition",
            json={"to": new_status},
        )
    except MadeUpTasksAPIError as exc:
        return _json({"error": str(exc)})

    # Build contextual hints based on the task's state after transition
    hints: list[str] = []

    if not task.get("assignee_id") and new_status == "in_progress":
        hints.append("This task has no assignee — it's now in progress but nobody is responsible for it.")

    if task.get("due_date") and _is_overdue(task["due_date"]):
        hints.append(f"This task is past its due date ({task['due_date']}).")

    if new_status == "done":
        hints.append("Task is now closed. No further transitions are possible.")

    result = {
        "task_id": task_id,
        "task_title": data.get("title"),
        "previous_status": data.get("previous_status"),
        "new_status": data.get("new_status"),
        "available_next_transitions": VALID_TRANSITIONS.get(data.get("new_status", ""), []),
        "timestamp": data.get("updated_at"),
    }
    if hints:
        result["hints"] = hints
    return _json(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 5: create_task
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def create_task(
    project_id: str,
    title: str,
    description: str | None = None,
    assignee: str | None = None,
    priority: str = "medium",
    due_date: str | None = None,
) -> str:
    """Create a new task in a project. Assignee can be specified by name.

    Returns confirmation with the created task's key fields.
    """
    client = _get_client()

    try:
        assignee_id = None
        if assignee:
            assignee_id = await resolve_user_name(client, assignee)
    except ValueError as exc:
        return _json({"error": str(exc)})

    payload: dict[str, Any] = {"title": title, "priority": priority}
    if description:
        payload["description"] = description
    if assignee_id:
        payload["assignee_id"] = assignee_id
    if due_date:
        payload["due_date"] = due_date

    try:
        data = await client.post(f"/projects/{project_id}/tasks", json=payload)
    except MadeUpTasksAPIError as exc:
        return _json({"error": str(exc)})

    assignee_name = await _resolve_assignee_name(client, data.get("assignee_id"))

    result = {
        "created": True,
        "task": {
            "id": data.get("id"),
            "title": data.get("title"),
            "status": data.get("status"),
            "assignee": assignee_name,
            "project_id": project_id,
            "priority": data.get("priority"),
            "due_date": data.get("due_date"),
        },
    }
    return _json(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 6: add_comment
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def add_comment(task_id: str, comment: str) -> str:
    """Add a comment to a task.

    Returns the comment ID, author, timestamp, and body preview.
    """
    client = _get_client()

    try:
        data = await client.post(
            f"/tasks/{task_id}/comments",
            json={"body": comment},
        )
    except MadeUpTasksAPIError as exc:
        return _json({"error": str(exc)})

    author_name = await _resolve_assignee_name(client, data.get("author_id"))

    result = {
        "comment_id": data.get("id"),
        "task_id": task_id,
        "author": author_name,
        "timestamp": data.get("created_at"),
        "body_preview": (data.get("body") or comment)[:200],
    }
    return _json(result)
