from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.api.auth.api_key import verify_api_key
from src.api.auth.session import SESSION_USER_ID_KEY
from src.core.database import get_db
from src.models.user import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> User:
    session_user_id = request.session.get(SESSION_USER_ID_KEY)
    if session_user_id:
        user = db.get(User, session_user_id)
        if user and user.is_active:
            request.state.auth_method = "session"
            return user

    if x_api_key:
        api_key = verify_api_key(db, x_api_key)
        if api_key is not None:
            user = db.get(User, api_key.user_id)
            if user and user.is_active:
                request.state.auth_method = "api_key"
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_roles(*roles: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency
