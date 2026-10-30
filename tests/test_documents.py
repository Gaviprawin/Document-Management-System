from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
import app.api.routes.documents as document_routes
import app.services.documents as document_service


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


@asynccontextmanager
async def app_test_lifespan(app):
    yield


app.router.lifespan_context = app_test_lifespan
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        document_service,
        "STORAGE_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        document_routes,
        "STORAGE_DIR",
        tmp_path,
    )

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "docuser",
            "email": "docuser@example.com",
            "password": "StrongPass123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "docuser@example.com",
            "password": "StrongPass123!",
        },
    )

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def test_upload_document(client, auth_headers):
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "hello.txt",
                b"Hello document management",
                "text/plain",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["original_filename"] == "hello.txt"
    assert response.json()["size_bytes"] == len(
        b"Hello document management"
    )

def test_upload_rejects_unsupported_extension(client, auth_headers):
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "script.exe",
                b"not an allowed file",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 415


def test_upload_requires_authentication(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": ("hello.txt", b"Hello", "text/plain")
        },
    )

    assert response.status_code == 401


def test_list_and_download_document(client, auth_headers):
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "notes.txt",
                b"My private notes",
                "text/plain",
            )
        },
    )

    assert upload.status_code == 201
    document_id = upload.json()["id"]

    listing = client.get(
        "/api/v1/documents/?page=1&page_size=10",
        headers=auth_headers,
    )

    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    download = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth_headers,
    )

    assert download.status_code == 200
    assert download.content == b"My private notes"


def test_delete_document(client, auth_headers):
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "remove.txt",
                b"Delete this document",
                "text/plain",
            )
        },
    )

    document_id = upload.json()["id"]

    deletion = client.delete(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )

    assert deletion.status_code == 204

    details = client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )

    assert details.status_code == 404


def test_multiple_upload(client, auth_headers):
    response = client.post(
        "/api/v1/documents/upload-multiple",
        headers=auth_headers,
        files=[
            ("files", ("first.txt", b"First file", "text/plain")),
            ("files", ("second.txt", b"Second file", "text/plain")),
        ],
    )

    assert response.status_code == 201
    assert len(response.json()) == 2
