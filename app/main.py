
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.shares import router as shares_router
from app.api.routes.admin import router as admin_router
from app.api.routes.audit import router as audit_router

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter

from app.db.base import Base
from app.db.session import engine

from app.middleware.request_logging import RequestLoggingMiddleware

# Import all models so SQLAlchemy registers their tables.
from app.models import User, Document, DocumentShare, AuditLog


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Development setup. Use Alembic for versioned schema changes.
    Base.metadata.create_all(bind=engine)

    yield

    engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="Secure document management and file-sharing API",
    version="1.0.0",
    lifespan=lifespan,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

register_exception_handlers(app)
app.add_middleware(RequestLoggingMiddleware)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(shares_router)
app.include_router(admin_router)
app.include_router(audit_router)


@app.get("/", tags=["Health"])
def home():
    return {
        "message": "Document Management API is running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Explicitly configure Swagger UI's multiple-file upload field.
    operation = (
        openapi_schema
        .get("paths", {})
        .get("/api/v1/documents/upload-multiple", {})
        .get("post", {})
    )

    request_body = operation.get("requestBody", {})
    multipart = request_body.get("content", {}).get(
        "multipart/form-data", {}
    )
    body_schema = multipart.get("schema", {})

    # FastAPI may store the request body schema under components/$ref.
    if "$ref" in body_schema:
        schema_name = body_schema["$ref"].rsplit("/", 1)[-1]
        body_schema = (
            openapi_schema
            .get("components", {})
            .get("schemas", {})
            .get(schema_name, body_schema)
        )

    if body_schema:
        body_schema.setdefault("type", "object")
        body_schema.setdefault("properties", {})
        body_schema["properties"]["files"] = {
            "type": "array",
            "items": {
                "type": "string",
                "format": "binary",
            },
        }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
