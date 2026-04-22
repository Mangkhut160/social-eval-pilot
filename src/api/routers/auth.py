from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.api.auth.api_key import create_api_key
from src.api.auth.dependencies import get_current_user
from src.api.auth.password import hash_password, verify_password
from src.api.auth.session import login_user, logout_user
from src.api.schemas.auth import (
    AcceptInvitationRequest,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    LoginRequest,
)
from src.api.schemas.users import UserResponse
from src.core.database import get_db
from src.core.time import utc_now
from src.models.user import Invitation, User

router = APIRouter()


def _build_user_response(user: User, *, auth_method: str | None = None) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at,
        auth_method=auth_method,
    )


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    login_user(request, user)
    return _build_user_response(user, auth_method="session")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    _: User = Depends(get_current_user),
) -> Response:
    logout_user(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def me(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    auth_method = getattr(request.state, "auth_method", None)
    return _build_user_response(current_user, auth_method=auth_method)


@router.post(
    "/invitations/accept",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def accept_invitation(
    payload: AcceptInvitationRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    invitation = db.query(Invitation).filter(Invitation.token == payload.token).first()
    if invitation is None or invitation.is_used:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )
    if invitation.expires_at < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired",
        )
    existing_user = db.query(User).filter(User.email == invitation.email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    user = User(
        email=invitation.email,
        display_name=payload.display_name,
        hashed_password=hash_password(payload.password),
        role=invitation.role,
        is_active=True,
    )
    invitation.is_used = True
    db.add(user)
    db.add(invitation)
    db.commit()
    db.refresh(user)
    return _build_user_response(user)


@router.post(
    "/api-keys",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_api_key(
    payload: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyResponse:
    api_key, raw_key = create_api_key(
        db,
        user_id=current_user.id,
        name=payload.name,
    )
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        api_key=raw_key,
        created_at=api_key.created_at,
    )
