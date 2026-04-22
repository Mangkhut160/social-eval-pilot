from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.database import get_db
from src.core.time import utc_now
from src.models.user import Invitation
from tests.test_api.conftest import create_user


@contextmanager
def custom_client(
    db_session: Session,
    app_settings: Settings,
) -> Generator[TestClient, None, None]:
    from src.api.main import create_app

    app = create_app(app_settings=app_settings)

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            db_session.rollback()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_admin_can_invite_user_activate_account_and_login(
    client: TestClient, db_session: Session
) -> None:
    create_user(
        db_session,
        email="admin@example.com",
        role="admin",
        display_name="Admin",
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    invite_response = client.post(
        "/api/users/invitations",
        json={"email": "editor@example.com", "role": "editor"},
    )
    assert invite_response.status_code == 201
    token = invite_response.json()["token"]

    activation_response = client.post(
        "/api/auth/invitations/accept",
        json={
            "token": token,
            "display_name": "Editor User",
            "password": "new-password-123",
        },
    )
    assert activation_response.status_code == 201
    assert activation_response.json()["email"] == "editor@example.com"
    assert activation_response.json()["role"] == "editor"

    client.cookies.clear()
    invited_login = client.post(
        "/api/auth/login",
        json={"email": "editor@example.com", "password": "new-password-123"},
    )
    assert invited_login.status_code == 200
    assert invited_login.json()["email"] == "editor@example.com"

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "editor@example.com"
    assert me_response.json()["display_name"] == "Editor User"
    assert me_response.json()["auth_method"] == "session"


def test_admin_can_list_and_revoke_unused_invitations(
    client: TestClient, db_session: Session
) -> None:
    create_user(
        db_session,
        email="admin@example.com",
        role="admin",
        display_name="Admin",
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    first_invite_response = client.post(
        "/api/users/invitations",
        json={"email": "expert@example.com", "role": "expert"},
    )
    assert first_invite_response.status_code == 201
    first_invitation_id = first_invite_response.json()["id"]

    second_invite_response = client.post(
        "/api/users/invitations",
        json={"email": "editor@example.com", "role": "editor"},
    )
    assert second_invite_response.status_code == 201
    used_invitation_token = second_invite_response.json()["token"]

    accept_response = client.post(
        "/api/auth/invitations/accept",
        json={
            "token": used_invitation_token,
            "display_name": "Editor User",
            "password": "new-password-123",
        },
    )
    assert accept_response.status_code == 201

    list_response = client.get("/api/users/invitations")
    assert list_response.status_code == 200
    invitations = list_response.json()["items"]
    assert len(invitations) == 1
    assert invitations[0]["email"] == "expert@example.com"
    assert all(item["is_used"] is False for item in invitations)

    revoke_response = client.delete(f"/api/users/invitations/{first_invitation_id}")
    assert revoke_response.status_code == 204

    list_after_revoke_response = client.get("/api/users/invitations")
    assert list_after_revoke_response.status_code == 200
    remaining_invitations = list_after_revoke_response.json()["items"]
    assert remaining_invitations == []


def test_expired_unused_invitation_does_not_block_new_invitation(
    client: TestClient, db_session: Session
) -> None:
    admin = create_user(
        db_session,
        email="admin@example.com",
        role="admin",
        display_name="Admin",
    )
    expired_invitation = Invitation(
        email="expert@example.com",
        role="expert",
        token="expired-token",
        invited_by=admin.id,
        is_used=False,
        expires_at=utc_now() - timedelta(days=1),
    )
    db_session.add(expired_invitation)
    db_session.commit()

    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    invite_response = client.post(
        "/api/users/invitations",
        json={"email": "expert@example.com", "role": "expert"},
    )
    assert invite_response.status_code == 201
    assert invite_response.json()["token"] != "expired-token"


def test_api_key_can_access_protected_route(
    client: TestClient, db_session: Session
) -> None:
    create_user(
        db_session,
        email="editor@example.com",
        role="editor",
        display_name="Editor",
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "editor@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    api_key_response = client.post(
        "/api/auth/api-keys",
        json={"name": "integration"},
    )
    assert api_key_response.status_code == 201
    raw_api_key = api_key_response.json()["api_key"]

    client.cookies.clear()
    me_response = client.get(
        "/api/auth/me",
        headers={"X-API-Key": raw_api_key},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "editor@example.com"
    assert me_response.json()["auth_method"] == "api_key"


def test_login_rejects_invalid_credentials(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="admin@example.com", role="admin")

    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_health_endpoint_is_available_without_auth(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_production_settings_require_non_default_secret_key() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            app_env="production",
            allowed_origins=["https://app.socialeval.example"],
            public_base_url="https://app.socialeval.example",
            api_base_url="https://api.socialeval.example",
        )


def test_production_login_sets_secure_cookie_and_domain(
    db_session: Session,
) -> None:
    create_user(db_session, email="admin@example.com", role="admin")

    app_settings = Settings(
        app_env="production",
        secret_key="production-secret-key",
        allowed_origins=["https://app.socialeval.example"],
        session_cookie_secure=True,
        session_cookie_domain="socialeval.example",
        public_base_url="https://app.socialeval.example",
        api_base_url="https://api.socialeval.example",
    )

    with custom_client(db_session, app_settings) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "secret123"},
        )

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"].lower()
    assert "secure" in set_cookie
    assert "domain=socialeval.example" in set_cookie


def test_cors_headers_follow_allowed_origins_setting(db_session: Session) -> None:
    app_settings = Settings(
        app_env="production",
        secret_key="production-secret-key",
        allowed_origins=["https://app.socialeval.example"],
        public_base_url="https://app.socialeval.example",
        api_base_url="https://api.socialeval.example",
    )

    with custom_client(db_session, app_settings) as client:
        allowed = client.get(
            "/api/health",
            headers={"Origin": "https://app.socialeval.example"},
        )
        denied = client.get(
            "/api/health",
            headers={"Origin": "https://evil.example.com"},
        )

    assert allowed.headers["access-control-allow-origin"] == "https://app.socialeval.example"
    assert "access-control-allow-origin" not in denied.headers
