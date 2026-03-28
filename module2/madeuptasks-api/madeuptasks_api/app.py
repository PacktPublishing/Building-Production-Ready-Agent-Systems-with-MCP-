from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from .seed import load_seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_seed_data()
    yield


app = FastAPI(title="MadeUpTasks API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def latency_middleware(request: Request, call_next):
    """Add artificial latency for realism."""
    await asyncio.sleep(random.uniform(0.05, 0.3))
    response = await call_next(request)
    return response


# Import and register routers
from .routers import attachments, comments, health, projects, tasks, users  # noqa: E402

app.include_router(health.router, tags=["health"])
app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(comments.router, prefix="/api/v1", tags=["comments"])
app.include_router(attachments.router, prefix="/api/v1", tags=["attachments"])
