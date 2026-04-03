# backend/api/dependencies.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from backend.core.container import get_container, Container
from backend.core.security import decode_token
from backend.database import get_db

bearer_scheme = HTTPBearer()


# ── Container deps ───────────────────────────────────────────────────────────

def get_groq(container: Container = Depends(get_container)):
    return container.groq


def get_policy(container: Container = Depends(get_container)):
    return container.policy


def get_conversations(container: Container = Depends(get_container)):
    return container.conversations

# ── Auth deps ────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db:          AsyncIOMotorDatabase          = Depends(get_db),
) -> dict:
    """
    Extracts and validates JWT from Authorization header.
    Returns the full user document from DB.
    Inject this into any protected endpoint.
    """
    token   = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"password": 0, "lastRecommendations": 0}  # never return password
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    if not user.get("isActive", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Attach string id for convenience
    user["id"] = str(user["_id"])
    return user


async def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Same as get_current_user but requires role=admin.
    Use this to protect CRM dashboard endpoints.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
