from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Static bearer tokens mapped to user IDs
TOKEN_USER_MAP: dict[str, str] = {
    "tf_token_alice": "usr_001",
    "tf_token_bob": "usr_002",
    "tf_token_carol": "usr_003",
    "tf_token_dave": "usr_004",
    "tf_token_eve": "usr_005",
}

# Security scheme for Swagger UI
bearer_scheme = HTTPBearer(
    scheme_name="Bearer Token",
    description="Enter one of the static tokens: tf_token_alice, tf_token_bob, tf_token_carol, tf_token_dave, tf_token_eve",
)


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> str:
    """Extract user ID from bearer token."""
    token = credentials.credentials
    user_id = TOKEN_USER_MAP.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return user_id


def make_meta() -> dict[str, Any]:
    return {
        "request_id": f"req_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def success_response(data: Any, pagination: dict[str, Any] | None = None) -> dict[str, Any]:
    resp: dict[str, Any] = {"data": data, "meta": make_meta()}
    if pagination is not None:
        resp["pagination"] = pagination
    return resp


def error_response(code: str, message: str, details: dict[str, Any] | None = None, status: int = 400) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {"code": code, "message": message},
        "meta": make_meta(),
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)
