from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from src.core.time import utc_now


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    display_name: str | None = None
    is_active: bool
    created_at: datetime
    auth_method: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    items: list[UserResponse]


class InvitationCreateRequest(BaseModel):
    email: str
    role: str = Field(pattern="^(submitter|editor|expert|admin)$")
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    token: str
    expires_at: datetime


class InvitationListItem(BaseModel):
    id: str
    email: str
    role: str
    token: str
    invited_by: str
    is_used: bool
    expires_at: datetime
    created_at: datetime


class InvitationListResponse(BaseModel):
    items: list[InvitationListItem]


def default_expiration(days: int) -> datetime:
    return utc_now() + timedelta(days=days)
