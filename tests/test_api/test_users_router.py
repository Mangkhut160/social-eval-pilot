from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_api.conftest import create_user


def test_users_route_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/users")

    assert response.status_code == 401


def test_non_admin_cannot_list_users(client: TestClient, db_session: Session) -> None:
    create_user(db_session, email="editor@example.com", role="editor")

    login_response = client.post(
        "/api/auth/login",
        json={"email": "editor@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    response = client.get("/api/users")

    assert response.status_code == 403


def test_admin_can_list_users(client: TestClient, db_session: Session) -> None:
    create_user(db_session, email="admin@example.com", role="admin")
    create_user(
        db_session,
        email="submitter@example.com",
        role="submitter",
        display_name="Submitter",
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    response = client.get("/api/users")

    assert response.status_code == 200
    emails = [item["email"] for item in response.json()["items"]]
    assert "admin@example.com" in emails
    assert "submitter@example.com" in emails
