"""Async HTTP wrapper around the MadeUpTasks REST API."""

from __future__ import annotations

import os
from typing import Any

import httpx


class MadeUpTasksAPIError(Exception):
    """Raised when the MadeUpTasks API returns an error."""


class MadeUpTasksClient:
    """Lightweight async client for the MadeUpTasks API.

    Configuration is read from environment variables:
      - MADEUPTASKS_API_URL   (default: http://localhost:8090/api/v1)
      - MADEUPTASKS_API_TOKEN (required)
    """

    def __init__(self) -> None:
        self.base_url: str = os.environ.get(
            "MADEUPTASKS_API_URL", "http://localhost:8090/api/v1"
        ).rstrip("/")
        self.token: str = os.environ.get("MADEUPTASKS_API_TOKEN", "")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Send a GET request and return the unwrapped data payload."""
        resp = await self._request("GET", path, params=params)
        return _unwrap(resp)

    async def get_raw(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Send a GET request and return the full response body (with pagination)."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        """Send a POST request and return the unwrapped data payload."""
        resp = await self._request("POST", path, json=json)
        return _unwrap(resp)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        try:
            resp = await self._client.request(method, path, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MadeUpTasksAPIError(_friendly_error(exc)) from exc
        except httpx.RequestError as exc:
            raise MadeUpTasksAPIError(
                f"Network error contacting MadeUpTasks API: {exc}"
            ) from exc
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()


def _unwrap(body: Any) -> Any:
    """Extract the data field from the standard API envelope."""
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def _friendly_error(exc: httpx.HTTPStatusError) -> str:
    """Convert an HTTP error into an agent-friendly message."""
    status = exc.response.status_code
    try:
        detail = exc.response.json()
        msg = detail.get("error", {}).get("message") or detail.get("message") or str(detail)
    except Exception:
        msg = exc.response.text[:300]

    if status == 401:
        return "Authentication failed. Check MADEUPTASKS_API_TOKEN."
    if status == 403:
        return f"Permission denied: {msg}"
    if status == 404:
        return f"Resource not found: {msg}"
    if status == 409:
        return f"Conflict: {msg}"
    if status == 422:
        return f"Validation error: {msg}"
    return f"MadeUpTasks API error ({status}): {msg}"
