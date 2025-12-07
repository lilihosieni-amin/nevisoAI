from typing import Optional
from fastapi import Depends, HTTPException, status, Cookie, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import verify_token
from app.crud import user as user_crud

security = HTTPBearer(auto_error=False)


async def get_current_user_from_token(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Get current user from JWT token in Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    token = authorization.credentials
    payload = verify_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    user = await user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


async def get_current_user_from_cookie(
    request: Request,
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """Get current user from JWT token in cookie (for frontend pages)"""
    # --- DEBUGGING START ---
    print("\n--- [DEBUG] Attempting to get user from cookie for request to:", request.url.path)
    token_from_request_cookies = request.cookies.get("access_token")
    
    if not token_from_request_cookies:
        print("--- [DEBUG] FAILED: 'access_token' cookie NOT found in request.cookies.")
    else:
        print(f"--- [DEBUG] SUCCESS: 'access_token' cookie FOUND in request.cookies. Value starts with: {token_from_request_cookies[:15]}...")

    if not access_token:
        print("--- [DEBUG] FAILED: FastAPI's Cookie() dependency could NOT find the token.\n")
        return None
    # --- DEBUGGING END ---

    try:
        payload = verify_token(access_token)
    except Exception as e:
        print(f"--- [DEBUG] ERROR: Token verification failed with an exception: {e}\n")
        return None

    if not payload or payload.get("type") != "access":
        print(f"--- [DEBUG] WARNING: Invalid payload or token type. Payload: {payload}\n")
        return None

    user_id: int = payload.get("sub")
    if user_id is None:
        print(f"--- [DEBUG] WARNING: User ID ('sub') not in token payload.\n")
        return None

    user = await user_crud.get_user_by_id(db, user_id)
    if user is None:
        print(f"--- [DEBUG] WARNING: User with ID {user_id} not found in DB.\n")
        return None

    print(f"--- [DEBUG] SUCCESS: Authenticated user {user.id} from cookie.\n")
    return user


async def get_optional_current_user(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Get current user if authenticated, otherwise return None"""
    if not authorization:
        return None

    token = authorization.credentials
    payload = verify_token(token)

    if not payload or payload.get("type") != "access":
        return None

    user_id: int = payload.get("sub")
    if user_id is None:
        return None

    user = await user_crud.get_user_by_id(db, user_id)
    return user