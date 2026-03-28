from fastapi import APIRouter, Depends, Query

from ..auth import get_current_user_id, success_response
from ..store import store

router = APIRouter()


@router.get("/users")
async def list_users(
    role: str | None = None,
    team_id: str | None = None,
    name: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _user_id: str = Depends(get_current_user_id),
):
    users = list(store.users.values())
    if role:
        users = [u for u in users if u.role == role]
    if team_id:
        users = [u for u in users if u.team_id == team_id]
    if name:
        name_lower = name.lower()
        users = [u for u in users if name_lower in u.name.lower()]

    total = len(users)
    page = users[offset : offset + limit]
    return success_response(
        [u.model_dump() for u in page],
        pagination={"limit": limit, "offset": offset, "total": total},
    )


@router.get("/users/me")
async def get_current_user(user_id: str = Depends(get_current_user_id)):
    user = store.users.get(user_id)
    if not user:
        return {"error": {"code": "NOT_FOUND", "message": "Current user not found"}}
    return success_response(user.model_dump())


@router.get("/users/{user_id}")
async def get_user(user_id: str, _caller: str = Depends(get_current_user_id)):
    user = store.users.get(user_id)
    if not user:
        return {"error": {"code": "NOT_FOUND", "message": f"User '{user_id}' not found"}}
    return success_response(user.model_dump())
