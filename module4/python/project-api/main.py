"""
Module 4 - Mock Project Management API
FastAPI service with JWT validation via Keycloak.
Demonstrates scope-gated endpoints for the permission delegation workshop.
"""

import os
import logging
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "workshop")
EXPECTED_AUDIENCE = os.getenv("EXPECTED_AUDIENCE", "project-api")
PORT = int(os.getenv("PORT", "3000"))

JWKS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
ISSUER_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger("project-api")

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TASKS: dict[str, dict] = {
    "TASK-001": {
        "id": "TASK-001",
        "title": "Update API documentation",
        "assignee": "alice",
        "status": "open",
        "priority": "medium",
    },
    "TASK-002": {
        "id": "TASK-002",
        "title": "Fix login page CSS",
        "assignee": "bob",
        "status": "open",
        "priority": "high",
    },
    "TASK-003": {
        "id": "TASK-003",
        "title": "Add unit tests for auth module",
        "assignee": "alice",
        "status": "open",
        "priority": "high",
    },
    "TASK-004": {
        "id": "TASK-004",
        "title": "Set up CI/CD pipeline",
        "assignee": "bob",
        "status": "in-progress",
        "priority": "critical",
    },
    "TASK-005": {
        "id": "TASK-005",
        "title": "Review pull request #42",
        "assignee": "alice",
        "status": "open",
        "priority": "low",
    },
}

_next_id = 6  # for creating new tasks

# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

_jwks_cache: dict | None = None


async def _fetch_jwks() -> dict:
    """Fetch and cache the JWKS key set from Keycloak."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    logger.info("Fetching JWKS from %s", JWKS_URL)
    async with httpx.AsyncClient() as client:
        resp = await client.get(JWKS_URL)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        logger.info("JWKS fetched successfully (%d keys)", len(_jwks_cache.get("keys", [])))
        return _jwks_cache


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

security = HTTPBearer()


async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Validate the JWT and return its decoded claims."""
    token = credentials.credentials
    try:
        jwks = await _fetch_jwks()
        # Decode the header to find the right key
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        rsa_key = None
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                rsa_key = key_data
                break

        if rsa_key is None:
            # Invalidate cache and retry once (key rotation)
            global _jwks_cache
            _jwks_cache = None
            jwks = await _fetch_jwks()
            for key_data in jwks.get("keys", []):
                if key_data.get("kid") == kid:
                    rsa_key = key_data
                    break

        if rsa_key is None:
            raise HTTPException(status_code=401, detail="Unable to find matching signing key")

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE,
            issuer=ISSUER_URL,
            options={"verify_aud": True, "verify_iss": True},
        )
        azp = payload.get("azp", "unknown")
        act = payload.get("act", {})
        actor_sub = act.get("sub", "none") if act else "none"
        logger.info(
            "Token validated: user=%s  azp=%s  actor=%s  scopes=%s",
            payload.get("preferred_username", "unknown"),
            azp,
            actor_sub,
            payload.get("scope", ""),
        )
        return payload

    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch JWKS: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to validate token (JWKS fetch failed)")


def require_scope(required: str):
    """Return a dependency that checks for a specific scope in the validated token."""

    async def _check(claims: dict = Depends(validate_token)):
        scopes = claims.get("scope", "").split()
        if required not in scopes:
            logger.warning(
                "Scope check FAILED: user=%s required=%s has=%s",
                claims.get("preferred_username", "unknown"),
                required,
                scopes,
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Insufficient scope. This endpoint requires '{required}'. "
                    f"Your token has: [{', '.join(scopes)}]. "
                    f"Contact your administrator to request the '{required}' scope."
                ),
            )
        return claims

    return _check


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Project Management API",
    description="Mock project API for Module 4 - Permission Delegation and Security",
    version="1.0.0",
)


class TaskCreate(BaseModel):
    title: str
    assignee: Optional[str] = None
    priority: Optional[str] = "medium"


# -- Health -----------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# -- Endpoints --------------------------------------------------------------

@app.get("/tasks")
async def list_tasks(claims: dict = Depends(require_scope("tasks:read"))):
    """List all tasks. Requires tasks:read scope."""
    logger.info("GET /tasks  user=%s", claims.get("preferred_username"))
    return list(TASKS.values())


@app.get("/tasks/{task_id}")
async def get_task(task_id: str, claims: dict = Depends(require_scope("tasks:read"))):
    """Get a single task by ID. Requires tasks:read scope."""
    logger.info("GET /tasks/%s  user=%s", task_id, claims.get("preferred_username"))
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.post("/tasks", status_code=201)
async def create_task(body: TaskCreate, claims: dict = Depends(require_scope("tasks:admin"))):
    """Create a new task. Requires tasks:admin scope."""
    global _next_id
    task_id = f"TASK-{_next_id:03d}"
    _next_id += 1
    task = {
        "id": task_id,
        "title": body.title,
        "assignee": body.assignee or claims.get("preferred_username", "unassigned"),
        "status": "open",
        "priority": body.priority or "medium",
    }
    TASKS[task_id] = task
    logger.info("POST /tasks  created=%s  user=%s", task_id, claims.get("preferred_username"))
    return task


@app.patch("/tasks/{task_id}/close")
async def close_task(task_id: str, claims: dict = Depends(require_scope("tasks:admin"))):
    """Close a task. Requires tasks:admin scope."""
    logger.info("PATCH /tasks/%s/close  user=%s", task_id, claims.get("preferred_username"))
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    task["status"] = "closed"
    return task


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Project API on port %d", PORT)
    logger.info("Keycloak: %s  Realm: %s  Audience: %s", KEYCLOAK_URL, KEYCLOAK_REALM, EXPECTED_AUDIENCE)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
