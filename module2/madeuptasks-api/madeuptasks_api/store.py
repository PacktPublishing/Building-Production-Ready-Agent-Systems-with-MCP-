from __future__ import annotations

from .models import Attachment, Comment, Project, ProjectMember, Task, User


class DataStore:
    """In-memory data store for all MadeUpTasks entities."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.projects: dict[str, Project] = {}
        self.project_members: list[ProjectMember] = []
        self.tasks: dict[str, Task] = {}
        self.comments: dict[str, Comment] = {}
        self.attachments: dict[str, Attachment] = {}
        self._next_task_num: int = 36
        self._next_comment_num: int = 21
        self._next_attachment_num: int = 6

    def next_task_id(self) -> str:
        tid = f"tsk_{self._next_task_num:03d}"
        self._next_task_num += 1
        return tid

    def next_comment_id(self) -> str:
        cid = f"cmt_{self._next_comment_num:03d}"
        self._next_comment_num += 1
        return cid

    def next_attachment_id(self) -> str:
        aid = f"att_{self._next_attachment_num:03d}"
        self._next_attachment_num += 1
        return aid


# Global singleton
store = DataStore()
