"""Helper utilities for status normalization, user resolution, and state transitions."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api_client import MadeUpTasksClient

# ── Valid state transitions (MadeUpTasks state machine) ────────────────────────
VALID_TRANSITIONS: dict[str, list[str]] = {
    "open": ["in_progress", "blocked"],
    "in_progress": ["in-review", "blocked"],
    "in-review": ["done", "in_progress"],
    "blocked": ["open", "in_progress"],
    "done": [],
}

# ── Status normalization map ─────────────────────────────────────────────────
_STATUS_ALIASES: dict[str, str] = {
    "open": "open",
    "opened": "open",
    "new": "open",
    "todo": "open",
    "to do": "open",
    "to_do": "open",
    "in_progress": "in_progress",
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "inprogress": "in_progress",
    "wip": "in_progress",
    "working": "in_progress",
    "in_review": "in-review",
    "in review": "in-review",
    "in-review": "in-review",
    "inreview": "in-review",
    "review": "in-review",
    "reviewing": "in-review",
    "done": "done",
    "closed": "done",
    "complete": "done",
    "completed": "done",
    "finished": "done",
    "resolved": "done",
    "blocked": "blocked",
    "stuck": "blocked",
}


def normalize_status(status: str) -> str:
    """Map any casing/format of a status string to the canonical form.

    Canonical forms: open, in_progress, in_review, done, blocked.
    Raises ValueError with a helpful message when the status is unrecognised.
    """
    if status is None:
        raise ValueError("Status cannot be None.")
    key = re.sub(r"[\s_-]+", " ", status.strip().lower())
    canonical = _STATUS_ALIASES.get(key)
    if canonical is None:
        valid = ", ".join(sorted(set(_STATUS_ALIASES.values())))
        raise ValueError(
            f"Unrecognised status '{status}'. Valid statuses are: {valid}"
        )
    return canonical


# ── User name resolution with caching ────────────────────────────────────────
_USER_CACHE: dict[str, list[dict]] | None = None


async def _fetch_users(client: "MadeUpTasksClient") -> list[dict]:
    """Fetch and cache the full user list from the API."""
    global _USER_CACHE
    if _USER_CACHE is None:
        data = await client.get("/users")
        # The API may return a list directly or nested under a key
        if isinstance(data, list):
            _USER_CACHE = {"users": data}
        elif isinstance(data, dict) and "users" in data:
            _USER_CACHE = {"users": data["users"]}
        else:
            _USER_CACHE = {"users": data if isinstance(data, list) else []}
    return _USER_CACHE["users"]


def _is_user_id(value: str) -> bool:
    """Return True if the string looks like a MadeUpTasks user ID (usr_XXX)."""
    return bool(re.match(r"^usr_\w+$", value))


async def resolve_user_name(client: "MadeUpTasksClient", name: str) -> str:
    """Resolve a human-readable name to a MadeUpTasks user ID.

    If *name* already looks like a user ID (usr_XXX), return it unchanged.
    Otherwise, search by name (case-insensitive). On no match, raise a
    ValueError listing the available user names.
    """
    if _is_user_id(name):
        return name

    users = await _fetch_users(client)
    name_lower = name.strip().lower()

    # Try exact match first, then substring / partial
    for user in users:
        display = user.get("name", "") or user.get("display_name", "")
        if display.lower() == name_lower:
            return user["id"]

    # Partial / contains match
    for user in users:
        display = user.get("name", "") or user.get("display_name", "")
        if name_lower in display.lower():
            return user["id"]

    available = [u.get("name") or u.get("display_name", "?") for u in users]
    raise ValueError(
        f"Could not resolve user '{name}'. Available users: {', '.join(available)}"
    )
