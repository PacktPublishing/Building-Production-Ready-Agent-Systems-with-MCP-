"""Load and query the MadeUpTasks endpoint manifest."""

from __future__ import annotations

import json
from pathlib import Path

# ── Load manifest at module level ────────────────────────────────────────────

_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "endpoint_manifest.json"

with open(_MANIFEST_PATH, "r", encoding="utf-8") as _f:
    _MANIFEST: dict = json.load(_f)

_GROUPS: dict = _MANIFEST["groups"]


# ── Public query helpers ─────────────────────────────────────────────────────


def get_groups() -> list[dict]:
    """Return a list of group summaries: name, description, endpoint_count."""
    return [
        {
            "name": name,
            "description": group["description"],
            "endpoint_count": len(group["endpoints"]),
        }
        for name, group in _GROUPS.items()
    ]


def get_endpoints_by_group(group: str) -> list[dict] | None:
    """Return endpoint summaries for a group, or None if group not found.

    Performs case-insensitive matching on group names.
    """
    # Case-insensitive lookup
    for name, grp in _GROUPS.items():
        if name.lower() == group.lower():
            return [
                {
                    "method": ep["method"],
                    "path": ep["path"],
                    "summary": ep["summary"],
                }
                for ep in grp["endpoints"]
            ]
    return None


def search(query: str) -> list[dict]:
    """Search endpoints by keyword across summary, description, tags, and parameter names.

    Case-insensitive substring matching.  Returns a list of
    {group, method, path, summary} for every matching endpoint.
    """
    q = query.lower()
    results: list[dict] = []

    for group_name, group in _GROUPS.items():
        for ep in group["endpoints"]:
            # Build a single searchable blob for the endpoint
            searchable_parts = [
                ep.get("summary", ""),
                ep.get("description", ""),
                " ".join(ep.get("tags", [])),
            ]
            for param in ep.get("parameters", []):
                searchable_parts.append(param.get("name", ""))
                searchable_parts.append(param.get("description", ""))

            blob = " ".join(searchable_parts).lower()

            if q in blob:
                results.append(
                    {
                        "group": group_name,
                        "method": ep["method"],
                        "path": ep["path"],
                        "summary": ep["summary"],
                    }
                )

    return results


def get_detail(method: str, path: str) -> dict | None:
    """Return the full endpoint detail dict for a given method+path, or None.

    Path matching uses the *template* form (e.g. /projects/{id}), case-insensitive
    on the method.
    """
    method_upper = method.upper()
    for _group_name, group in _GROUPS.items():
        for ep in group["endpoints"]:
            if ep["method"] == method_upper and ep["path"] == path:
                return ep
    return None
