from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth import error_response, get_current_user_id, success_response
from ..models import Project, ProjectMember
from ..store import store

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    description: str
    owner_id: str | None = None
    default_task_template: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    owner_id: str | None = None
    default_task_template: str | None = None


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "member"


@router.get("/projects")
async def list_projects(
    status: str | None = None,
    owner_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _user_id: str = Depends(get_current_user_id),
):
    projects = list(store.projects.values())
    if status:
        projects = [p for p in projects if p.status == status]
    if owner_id:
        projects = [p for p in projects if p.owner_id == owner_id]

    total = len(projects)
    page = projects[offset : offset + limit]
    return success_response(
        [_project_dict(p) for p in page],
        pagination={"limit": limit, "offset": offset, "total": total},
    )


@router.post("/projects", status_code=201)
async def create_project(
    req: CreateProjectRequest,
    user_id: str = Depends(get_current_user_id),
):
    pid = f"prj_{len(store.projects) + 1:03d}"
    now = datetime.now(timezone.utc).isoformat()
    owner = req.owner_id or user_id
    project = Project(
        id=pid,
        name=req.name,
        description=req.description,
        status="active",
        owner_id=owner,
        default_task_template=req.default_task_template,
        created_at=now,
        updated_at=now,
    )
    project.internal = {
        "audit_created_by": user_id,
        "audit_modified_at": now,
        "internal_cost_center": "CC-0000-NEW",
    }
    store.projects[pid] = project
    store.project_members.append(ProjectMember(project_id=pid, user_id=owner, role="owner"))
    return success_response(_project_dict(project))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    _user_id: str = Depends(get_current_user_id),
):
    project = store.projects.get(project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project '{project_id}' not found", status=404)
    return success_response(_project_dict(project))


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    req: UpdateProjectRequest,
    _user_id: str = Depends(get_current_user_id),
):
    project = store.projects.get(project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project '{project_id}' not found", status=404)

    if req.name is not None:
        project.name = req.name
    if req.description is not None:
        project.description = req.description
    if req.status is not None:
        project.status = req.status
    if req.owner_id is not None:
        project.owner_id = req.owner_id
    if req.default_task_template is not None:
        project.default_task_template = req.default_task_template
    project.updated_at = datetime.now(timezone.utc).isoformat()
    project.internal["audit_modified_at"] = project.updated_at

    return success_response(_project_dict(project))


@router.delete("/projects/{project_id}")
async def archive_project(
    project_id: str,
    _user_id: str = Depends(get_current_user_id),
):
    project = store.projects.get(project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project '{project_id}' not found", status=404)

    project.status = "archived"
    project.updated_at = datetime.now(timezone.utc).isoformat()
    return success_response({"id": project_id, "status": "archived"})


@router.get("/projects/{project_id}/members")
async def list_members(
    project_id: str,
    _user_id: str = Depends(get_current_user_id),
):
    if project_id not in store.projects:
        return error_response("NOT_FOUND", f"Project '{project_id}' not found", status=404)

    members = [pm for pm in store.project_members if pm.project_id == project_id]
    result = []
    for pm in members:
        user = store.users.get(pm.user_id)
        result.append({
            "user_id": pm.user_id,
            "role": pm.role,
            "name": user.name if user else "Unknown",
            "email": user.email if user else None,
        })
    return success_response(result)


@router.post("/projects/{project_id}/members", status_code=201)
async def add_member(
    project_id: str,
    req: AddMemberRequest,
    _user_id: str = Depends(get_current_user_id),
):
    if project_id not in store.projects:
        return error_response("NOT_FOUND", f"Project '{project_id}' not found", status=404)
    if req.user_id not in store.users:
        return error_response("NOT_FOUND", f"User '{req.user_id}' not found", status=404)

    store.project_members.append(ProjectMember(project_id=project_id, user_id=req.user_id, role=req.role))
    return success_response({"project_id": project_id, "user_id": req.user_id, "role": req.role})


@router.get("/projects/{project_id}/tasks")
async def list_project_tasks(
    project_id: str,
    status: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    _user_id: str = Depends(get_current_user_id),
):
    """List tasks in a project with cursor-based pagination."""
    if project_id not in store.projects:
        return error_response("NOT_FOUND", f"Project '{project_id}' not found", status=404)

    tasks = sorted(
        [t for t in store.tasks.values() if t.project_id == project_id],
        key=lambda t: t.created_at,
    )

    if status:
        normalized = _normalize_status(status)
        tasks = [t for t in tasks if t.status == normalized]
    if assignee_id:
        tasks = [t for t in tasks if t.assignee_id == assignee_id]
    if priority:
        tasks = [t for t in tasks if t.priority == priority.lower()]

    # Cursor-based pagination
    start_idx = 0
    if cursor:
        try:
            start_idx = int(base64.b64decode(cursor).decode())
        except Exception:
            return error_response("INVALID_CURSOR", "Invalid cursor value")

    page = tasks[start_idx : start_idx + limit]
    has_more = (start_idx + limit) < len(tasks)
    next_cursor = base64.b64encode(str(start_idx + limit).encode()).decode() if has_more else None

    return success_response(
        [t.to_response() for t in page],
        pagination={
            "next_cursor": next_cursor,
            "has_more": has_more,
        },
    )


def _project_dict(p: Project) -> dict:
    """Convert project to response dict including internal fields."""
    return p.to_response()


def _normalize_status(status: str) -> str:
    """Normalize status input to canonical form."""
    s = status.strip().lower().replace(" ", "_").replace("-", "_")
    mapping = {
        "open": "open",
        "in_progress": "in_progress",
        "in_review": "in-review",
        "done": "done",
        "blocked": "blocked",
    }
    return mapping.get(s, status.lower())
