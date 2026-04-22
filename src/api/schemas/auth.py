from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class AcceptInvitationRequest(BaseModel):
    token: str
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class ApiKeyCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)


class ApiKeyResponse(BaseModel):
    id: str
    name: str | None
    key_prefix: str
    api_key: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
