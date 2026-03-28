from fastapi import APIRouter

from ..store import store

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "seed_data_loaded": len(store.users) > 0,
        "entity_counts": {
            "users": len(store.users),
            "projects": len(store.projects),
            "tasks": len(store.tasks),
            "comments": len(store.comments),
            "attachments": len(store.attachments),
        },
    }
