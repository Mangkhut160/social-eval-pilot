from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.api.auth.dependencies import require_roles
from src.api.schemas.users import (
    InvitationCreateRequest,
    InvitationListItem,
    InvitationListResponse,
    InvitationResponse,
    UserListResponse,
    UserResponse,
    default_expiration,
)
from src.core.database import get_db
from src.core.time import utc_now
from src.models.user import Invitation, User

router = APIRouter()


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at,
        auth_method=None,
    )


@router.get("", response_model=UserListResponse)
def list_users(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> UserListResponse:
    users = db.query(User).order_by(User.created_at.asc()).all()
    return UserListResponse(items=[_user_response(user) for user in users])


@router.get("/experts", response_model=UserListResponse)
def list_experts(
    _: User = Depends(require_roles("editor", "admin")),
    db: Session = Depends(get_db),
) -> UserListResponse:
    users = db.query(User).filter(User.role == "expert").order_by(User.created_at.asc()).all()
    return UserListResponse(items=[_user_response(user) for user in users])


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    payload: InvitationCreateRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> InvitationResponse:
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    existing_invitation = (
        db.query(Invitation)
        .filter(
            Invitation.email == payload.email,
            Invitation.is_used.is_(False),
            Invitation.expires_at > utc_now(),
        )
        .first()
    )
    if existing_invitation is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active invitation already exists",
        )

    invitation = Invitation(
        email=payload.email,
        role=payload.role,
        token=secrets.token_urlsafe(32),
        invited_by=current_user.id,
        expires_at=default_expiration(payload.expires_in_days),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        expires_at=invitation.expires_at,
    )


@router.get("/invitations", response_model=InvitationListResponse)
def list_invitations(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> InvitationListResponse:
    invitations = (
        db.query(Invitation)
        .filter(Invitation.is_used.is_(False), Invitation.expires_at > utc_now())
        .order_by(Invitation.created_at.desc())
        .all()
    )
    return InvitationListResponse(
        items=[
            InvitationListItem(
                id=invitation.id,
                email=invitation.email,
                role=invitation.role,
                token=invitation.token,
                invited_by=invitation.invited_by,
                is_used=invitation.is_used,
                expires_at=invitation.expires_at,
                created_at=invitation.created_at,
            )
            for invitation in invitations
        ]
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: str,
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if invitation.is_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Used invitation cannot be revoked",
        )
    db.delete(invitation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
