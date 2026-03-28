import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth import error_response, get_current_user_id, success_response
from ..store import store

router = APIRouter()


class UploadAttachmentRequest(BaseModel):
    filename: str
    size: int
    mime_type: str


@router.get("/tasks/{task_id}/attachments")
async def list_attachments(
    task_id: str,
    _user_id: str = Depends(get_current_user_id),
):
    if task_id not in store.tasks:
        return error_response("NOT_FOUND", f"Task '{task_id}' not found", status=404)

    atts = [a for a in store.attachments.values() if a.task_id == task_id]
    return success_response([a.model_dump() for a in atts])


@router.post("/tasks/{task_id}/attachments", status_code=201)
async def upload_attachment_metadata(
    task_id: str,
    req: UploadAttachmentRequest,
    user_id: str = Depends(get_current_user_id),
):
    if task_id not in store.tasks:
        return error_response("NOT_FOUND", f"Task '{task_id}' not found", status=404)

    from datetime import datetime, timezone

    from ..models import Attachment

    att = Attachment(
        id=store.next_attachment_id(),
        task_id=task_id,
        filename=req.filename,
        size=req.size,
        mime_type=req.mime_type,
        uploaded_by=user_id,
        upload_date=datetime.now(timezone.utc).isoformat(),
    )
    store.attachments[att.id] = att

    upload_url = f"https://storage.madeuptasks.dev/upload/{att.id}/{uuid.uuid4().hex}"
    return success_response({"attachment": att.model_dump(), "upload_url": upload_url})


@router.get("/attachments/{attachment_id}/url")
async def get_download_url(
    attachment_id: str,
    _user_id: str = Depends(get_current_user_id),
):
    att = store.attachments.get(attachment_id)
    if not att:
        return error_response("NOT_FOUND", f"Attachment '{attachment_id}' not found", status=404)

    download_url = f"https://storage.madeuptasks.dev/download/{att.id}/{uuid.uuid4().hex}?expires=3600"
    return success_response({"attachment_id": att.id, "download_url": download_url, "expires_in": 3600})
