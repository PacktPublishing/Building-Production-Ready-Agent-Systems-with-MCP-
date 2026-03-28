from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import Attachment, Comment, Project, ProjectMember, Task, User
from .store import store

# Fields that go into Project.internal
_PROJECT_INTERNAL_KEYS = {"_audit_created_by", "_audit_modified_at", "_internal_cost_center"}

# Core Task fields (everything else goes into Task.extra)
_TASK_CORE_KEYS = {
    "id", "title", "description", "status", "priority", "assignee_id",
    "project_id", "due_date", "labels", "created_at", "updated_at",
}


def load_seed_data() -> None:
    """Load seed data from JSON fixture file into the in-memory store."""
    seed_path = os.environ.get(
        "SEED_DATA_PATH",
        str(Path(__file__).parent.parent / "seed_data.json"),
    )
    with open(seed_path) as f:
        data: dict[str, Any] = json.load(f)

    for u in data.get("users", []):
        store.users[u["id"]] = User(**u)

    for p in data.get("projects", []):
        internal = {k.lstrip("_"): p[k] for k in _PROJECT_INTERNAL_KEYS if k in p}
        core = {k: v for k, v in p.items() if k not in _PROJECT_INTERNAL_KEYS}
        proj = Project(**core, internal=internal)
        store.projects[proj.id] = proj

    for pm in data.get("project_members", []):
        store.project_members.append(ProjectMember(**pm))

    for t in data.get("tasks", []):
        core = {k: v for k, v in t.items() if k in _TASK_CORE_KEYS}
        extra = {k: v for k, v in t.items() if k not in _TASK_CORE_KEYS}
        task = Task(**core, extra=extra)
        store.tasks[task.id] = task

    for c in data.get("comments", []):
        store.comments[c["id"]] = Comment(**c)

    for a in data.get("attachments", []):
        store.attachments[a["id"]] = Attachment(**a)
