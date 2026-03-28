from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth import error_response, get_current_user_id, success_response
from ..models import Task
from ..store import store

router = APIRouter()

VALID_TRANSITIONS: dict[str, list[str]] = {
    "open": ["in_progress", "blocked"],
    "in_progress": ["in-review", "blocked"],
    "in-review": ["done", "in_progress"],
    "blocked": ["open", "in_progress"],
    "done": [],
}


def _normalize_status(status: str) -> str:
    s = status.strip().lower().replace(" ", "_").replace("-", "_")
    mapping = {
        "open": "open",
        "in_progress": "in_progress",
        "in_review": "in-review",
        "done": "done",
        "blocked": "blocked",
    }
    return mapping.get(s, status.lower())


class TransitionRequest(BaseModel):
    to: str


class CreateTaskRequest(BaseModel):
    title: str
    description: str | None = None
    assignee_id: str | None = None
    priority: str = "medium"
    due_date: str | None = None
    labels: list[str] | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: str | None = None
    priority: str | None = None
    due_date: str | None = None
    labels: list[str] | None = None


class BulkUpdateRequest(BaseModel):
    task_ids: list[str]
    updates: dict


@router.get("/tasks/search")
async def search_tasks(
    q: str | None = None,
    project_id: str | None = None,
    status: str | None = None,
    assignee_id: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    _user_id: str = Depends(get_current_user_id),
):
    """Search tasks globally with offset-based pagination."""
    tasks = list(store.tasks.values())

    if q:
        q_lower = q.lower()
        tasks = [
            t for t in tasks
            if q_lower in t.title.lower() or (t.description and q_lower in t.description.lower())
        ]
    if project_id:
        tasks = [t for t in tasks if t.project_id == project_id]
    if status:
        normalized = _normalize_status(status)
        tasks = [t for t in tasks if t.status == normalized]
    if assignee_id:
        tasks = [t for t in tasks if t.assignee_id == assignee_id]

    total = len(tasks)
    start = (page - 1) * per_page
    page_items = tasks[start : start + per_page]

    return success_response(
        [t.to_response() for t in page_items],
        pagination={"page": page, "per_page": per_page, "total": total},
    )


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    _user_id: str = Depends(get_current_user_id),
):
    task = store.tasks.get(task_id)
    if not task:
        return error_response("NOT_FOUND", f"No task found with ID '{task_id}'", status=404)
    return success_response(task.to_response())


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    req: UpdateTaskRequest,
    _user_id: str = Depends(get_current_user_id),
):
    task = store.tasks.get(task_id)
    if not task:
        return error_response("NOT_FOUND", f"No task found with ID '{task_id}'", status=404)

    if req.title is not None:
        task.title = req.title
    if req.description is not None:
        task.description = req.description
    if req.assignee_id is not None:
        task.assignee_id = req.assignee_id
    if req.priority is not None:
        task.priority = req.priority.lower()
    if req.due_date is not None:
        task.due_date = req.due_date
    if req.labels is not None:
        task.labels = req.labels
    task.updated_at = datetime.now(timezone.utc).isoformat()

    return success_response(task.to_response())


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    _user_id: str = Depends(get_current_user_id),
):
    """Hard delete — no undo. Intentionally dangerous for demo purposes."""
    task = store.tasks.pop(task_id, None)
    if not task:
        return error_response("NOT_FOUND", f"No task found with ID '{task_id}'", status=404)
    return success_response({"id": task_id, "deleted": True})


@router.post("/tasks/{task_id}/transition")
async def transition_task(
    task_id: str,
    req: TransitionRequest,
    _user_id: str = Depends(get_current_user_id),
):
    task = store.tasks.get(task_id)
    if not task:
        return error_response("NOT_FOUND", f"No task found with ID '{task_id}'", status=404)

    new_status = _normalize_status(req.to)
    current = task.status
    valid = VALID_TRANSITIONS.get(current, [])

    if new_status not in valid:
        return error_response(
            "INVALID_TRANSITION",
            f"Cannot transition from '{current}' to '{new_status}'. "
            f"Valid transitions: {', '.join(valid)}.",
            details={
                "current_status": current,
                "requested_status": new_status,
                "valid_transitions": valid,
            },
        )

    previous = task.status
    task.status = new_status
    task.updated_at = datetime.now(timezone.utc).isoformat()

    return success_response({
        "id": task_id,
        "title": task.title,
        "previous_status": previous,
        "new_status": new_status,
        "available_transitions": VALID_TRANSITIONS.get(new_status, []),
        "updated_at": task.updated_at,
    })


@router.post("/projects/{project_id}/tasks", status_code=201)
async def create_task(
    project_id: str,
    req: CreateTaskRequest,
    user_id: str = Depends(get_current_user_id),
):
    if project_id not in store.projects:
        return error_response("NOT_FOUND", f"Project '{project_id}' not found", status=404)

    now = datetime.now(timezone.utc).isoformat()
    task = Task(
        id=store.next_task_id(),
        title=req.title,
        description=req.description,
        status="open",
        priority=req.priority.lower(),
        assignee_id=req.assignee_id,
        project_id=project_id,
        due_date=req.due_date,
        labels=req.labels or [],
        created_at=now,
        updated_at=now,
    )
    store.tasks[task.id] = task
    return success_response(task.to_response())


@router.post("/tasks/bulk-update")
async def bulk_update_tasks(
    req: BulkUpdateRequest,
    _user_id: str = Depends(get_current_user_id),
):
    """Bulk update — returns only a count. Intentionally unhelpful for demo purposes."""
    if len(req.task_ids) > 100:
        return error_response("VALIDATION", "Maximum 100 tasks per bulk update")

    updated = 0
    for tid in req.task_ids:
        task = store.tasks.get(tid)
        if task:
            for key, val in req.updates.items():
                if hasattr(task, key):
                    setattr(task, key, val)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            updated += 1

    return success_response({"updated_count": updated})
