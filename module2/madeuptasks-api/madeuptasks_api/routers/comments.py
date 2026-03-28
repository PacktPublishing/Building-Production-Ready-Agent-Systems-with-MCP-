from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth import error_response, get_current_user_id, success_response
from ..models import Comment
from ..store import store

router = APIRouter()


class CreateCommentRequest(BaseModel):
    body: str
    parent_comment_id: str | None = None


@router.get("/tasks/{task_id}/comments")
async def list_comments(
    task_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _user_id: str = Depends(get_current_user_id),
):
    if task_id not in store.tasks:
        return error_response("NOT_FOUND", f"Task '{task_id}' not found", status=404)

    comments = sorted(
        [c for c in store.comments.values() if c.task_id == task_id],
        key=lambda c: c.created_at,
    )
    total = len(comments)
    page = comments[offset : offset + limit]
    return success_response(
        [c.model_dump() for c in page],
        pagination={"limit": limit, "offset": offset, "total": total},
    )


@router.post("/tasks/{task_id}/comments", status_code=201)
async def create_comment(
    task_id: str,
    req: CreateCommentRequest,
    user_id: str = Depends(get_current_user_id),
):
    if task_id not in store.tasks:
        return error_response("NOT_FOUND", f"Task '{task_id}' not found", status=404)

    comment = Comment(
        id=store.next_comment_id(),
        task_id=task_id,
        author_id=user_id,
        body=req.body,
        parent_comment_id=req.parent_comment_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    store.comments[comment.id] = comment
    return success_response(comment.model_dump())
