from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_application_openapi():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    data = response.json()

    assert "openapi" in data
    assert "paths" in data


def test_swagger_documentation():
    response = client.get("/docs")

    assert response.status_code == 200


def test_authentication_profile_requires_login():
    response = client.get("/api/v1/auth/me")

    assert response.status_code in (401, 403)


def test_documents_require_authentication():
    response = client.get("/api/v1/documents/")

    assert response.status_code in (401, 403)


def test_received_shares_require_authentication():
    response = client.get("/api/v1/shares/received")

    assert response.status_code in (401, 403)


def test_audit_logs_require_authentication():
    response = client.get("/api/v1/admin/audit-logs")

    assert response.status_code in (401, 403)


def test_multiple_upload_openapi_schema():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    upload_path = (
        schema["paths"]
        ["/api/v1/documents/upload-multiple"]
        ["post"]
    )

    assert "requestBody" in upload_path

    request_schema = (
        upload_path["requestBody"]
        ["content"]
        ["multipart/form-data"]
        ["schema"]
    )

    if "$ref" in request_schema:
        schema_name = request_schema["$ref"].split("/")[-1]

        request_schema = (
            schema["components"]["schemas"][schema_name]
        )

    files_schema = request_schema["properties"]["files"]

    assert files_schema["type"] == "array"
    assert files_schema["items"]["format"] == "binary"