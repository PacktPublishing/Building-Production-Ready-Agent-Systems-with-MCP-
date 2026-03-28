from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class User(BaseModel):
    id: str
    name: str
    email: str
    role: str
    team_id: str
    avatar_url: str


class Project(BaseModel):
    id: str
    name: str
    description: str
    status: str
    owner_id: str
    default_task_template: str | None = None
    created_at: str
    updated_at: str
    # Internal fields stored as a dict, serialized with _ prefix in responses
    internal: dict[str, Any] = Field(default_factory=dict, exclude=True)

    def to_response(self) -> dict[str, Any]:
        d = self.model_dump()
        d.pop("internal", None)
        # Add internal fields with _ prefix (intentional API noise)
        for k, v in self.internal.items():
            d[f"_{k}"] = v
        return d


class ProjectMember(BaseModel):
    project_id: str
    user_id: str
    role: str


class Task(BaseModel):
    id: str
    title: str
    description: str | None = None
    status: str
    priority: str
    assignee_id: str | None = None
    project_id: str
    due_date: str | None = None
    labels: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    # Noise fields — intentionally verbose, stored as dict
    extra: dict[str, Any] = Field(default_factory=dict, exclude=True)

    def to_response(self) -> dict[str, Any]:
        d = self.model_dump()
        d.pop("extra", None)
        # Merge extra fields directly (they already have proper keys)
        d.update(self.extra)
        return d


class Comment(BaseModel):
    id: str
    task_id: str
    author_id: str
    body: str
    parent_comment_id: str | None = None
    created_at: str


class Attachment(BaseModel):
    id: str
    task_id: str
    filename: str
    size: int
    mime_type: str
    uploaded_by: str | None = None
    upload_date: str
