"""Async HTTP client for the MadeUpTasks API."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

_BASE_URL = os.environ.get("MADEUPTASKS_API_URL", "http://localhost:8090/api/v1")
_TOKEN = os.environ.get("MADEUPTASKS_API_TOKEN", "")


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if _TOKEN:
        headers["Authorization"] = f"Bearer {_TOKEN}"
    return headers


async def request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute an HTTP request against the MadeUpTasks API and return the parsed JSON response.

    Parameters
    ----------
    method:  HTTP verb (GET, POST, PUT, DELETE, etc.)
    path:    Absolute path starting with / (e.g. /projects/prj_001)
    body:    Optional JSON body for POST/PUT requests.
    params:  Optional query-string parameters.

    Returns
    -------
    Parsed JSON body as a dict.  On non-JSON responses the raw text is
    wrapped in ``{"raw": "<text>"}``.
    """
    url = f"{_BASE_URL.rstrip('/')}{path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=method.upper(),
            url=url,
            headers=_headers(),
            json=body,
            params=params,
        )

    # Try to parse JSON; fall back to raw text
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        return {"raw": response.text, "status_code": response.status_code}
