from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import User, Document, DocumentShare


@asynccontextmanager
async def app_test_lifespan(app):
    yield


app.router.lifespan_context = app_test_lifespan

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    old_overrides = app.dependency_overrides.copy()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)


def register_user(client, username, email):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201, response.text


def login_user(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def set_user_role(email, role):
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.role = role
        db.commit()
    finally:
        db.close()


def upload_text_document(client, token):
    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "rbac-test.txt",
                b"RBAC document test",
                "text/plain",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_new_user_has_user_role(client):
    register_user(client, "roleuser", "roleuser@example.com")

    db = TestingSessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.email == "roleuser@example.com")
            .first()
        )
        assert user is not None
        assert user.role == "user"
    finally:
        db.close()


def test_regular_user_cannot_change_roles(client):
    register_user(client, "normaluser", "normal@example.com")
    token = login_user(client, "normal@example.com")

    response = client.patch(
        "/api/v1/admin/users/1/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )

    assert response.status_code == 403


def test_viewer_cannot_upload_documents(client):
    register_user(client, "vieweruser", "viewer@example.com")
    set_user_role("viewer@example.com", "viewer")
    token = login_user(client, "viewer@example.com")

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "viewer.txt",
                b"Viewer upload test",
                "text/plain",
            )
        },
    )

    assert response.status_code == 403


def test_read_share_does_not_allow_download(client):
    register_user(client, "owneruser", "owner@example.com")
    register_user(client, "recipientuser", "recipient@example.com")

    owner_token = login_user(client, "owner@example.com")
    recipient_token = login_user(client, "recipient@example.com")

    document_id = upload_text_document(client, owner_token)

    share_response = client.post(
        f"/api/v1/shares/documents/{document_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipient_email": "recipient@example.com",
            "permission": "read",
        },
    )

    assert share_response.status_code == 201, share_response.text

    received_response = client.get(
        "/api/v1/shares/received",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )

    assert received_response.status_code == 200
    assert any(
        item["document_id"] == document_id
        for item in received_response.json()
    )

    download_response = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )

    assert download_response.status_code == 403
