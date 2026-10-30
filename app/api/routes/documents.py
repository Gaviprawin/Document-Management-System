
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.rbac import StaffUser
from app.core.cache import (
    delete_cache_pattern,
    get_cached_json,
    set_cached_json,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.audit import record_audit
from app.services.documents import STORAGE_DIR, list_documents, save_document
from app.services.notifications import send_upload_notification
from app.services.permissions import (
    ensure_document_access,
    get_document_or_404,
)

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def invalidate_document_cache(user_id: int) -> None:
    delete_cache_pattern(f"documents:{user_id}:*")


def remove_stored_file(stored_filename: str) -> None:
    file_path = (STORAGE_DIR / stored_filename).resolve()

    if file_path.parent == STORAGE_DIR:
        file_path.unlink(missing_ok=True)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(...)],
    current_user: StaffUser,
    db: DbSession,
):
    document = None

    try:
        document = await save_document(db, file, current_user)

        record_audit(
            db=db,
            user_id=current_user.id,
            action="document.upload",
            resource_type="document",
            resource_id=str(document.id),
            ip_address=get_client_ip(request),
            details={
                "filename": document.original_filename,
                "size_bytes": document.size_bytes,
            },
        )

        db.commit()
        db.refresh(document)

    except Exception:
        db.rollback()

        if document is not None:
            remove_stored_file(document.stored_filename)

        raise

    invalidate_document_cache(current_user.id)

    background_tasks.add_task(
        send_upload_notification,
        current_user.email,
        document.original_filename,
    )

    return document


@router.post(
    "/upload-multiple",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_multiple_documents(
    request: Request,
    background_tasks: BackgroundTasks,
    files: Annotated[list[UploadFile], File(...)],
    current_user: StaffUser,
    db: DbSession,
):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Select at least one file",
        )

    if len(files) > settings.MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum {settings.MAX_FILES_PER_UPLOAD} files allowed"
            ),
        )

    saved_documents = []

    try:
        for upload in files:
            document = await save_document(
                db,
                upload,
                current_user,
            )
            saved_documents.append(document)

        for document in saved_documents:
            record_audit(
                db=db,
                user_id=current_user.id,
                action="document.upload",
                resource_type="document",
                resource_id=str(document.id),
                ip_address=get_client_ip(request),
                details={
                    "filename": document.original_filename,
                    "size_bytes": document.size_bytes,
                },
            )

        # Save all document rows and their audit records together.
        db.commit()

        for document in saved_documents:
            db.refresh(document)

    except Exception:
        db.rollback()

        for document in saved_documents:
            remove_stored_file(document.stored_filename)

        raise

    finally:
        for upload in files:
            await upload.close()

    invalidate_document_cache(current_user.id)

    for document in saved_documents:
        background_tasks.add_task(
            send_upload_notification,
            current_user.email,
            document.original_filename,
        )

    return saved_documents


@router.get(
    "/",
    response_model=DocumentListResponse,
)
def get_documents(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    content_type: str | None = None,
    sort_by: str = Query(
        "created_at",
        pattern="^(created_at|filename|size)$",
    ),
    order: str = Query(
        "desc",
        pattern="^(asc|desc)$",
    ),
):
    cache_key = (
        f"documents:{current_user.id}:"
        f"{page}:{page_size}:{search}:{content_type}:{sort_by}:{order}"
    )

    cached_data = get_cached_json(cache_key)

    if cached_data is not None:
        return cached_data

    result = list_documents(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        search=search,
        content_type=content_type,
        sort_by=sort_by,
        order=order,
    )

    result["items"] = [
        DocumentResponse.model_validate(document).model_dump(mode="json")
        for document in result["items"]
    ]

    set_cached_json(cache_key, result)

    return result


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    document = get_document_or_404(db, document_id)

    ensure_document_access(
        db,
        document,
        current_user,
        action="read",
    )

    return document


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    document = get_document_or_404(db, document_id)

    ensure_document_access(
        db,
        document,
        current_user,
        action="download",
    )

    file_path = (STORAGE_DIR / document.stored_filename).resolve()

    if file_path.parent != STORAGE_DIR:
        raise HTTPException(
            status_code=400,
            detail="Invalid storage path",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found on storage",
        )

    return FileResponse(
        path=file_path,
        filename=document.original_filename,
        media_type=document.content_type,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_document(
    document_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    document = get_document_or_404(db, document_id)

    ensure_document_access(
        db,
        document,
        current_user,
        action="delete",
    )

    stored_filename = document.stored_filename
    owner_id = document.owner_id

    try:
        record_audit(
            db=db,
            user_id=current_user.id,
            action="document.delete",
            resource_type="document",
            resource_id=str(document.id),
            ip_address=get_client_ip(request),
            details={
                "filename": document.original_filename,
            },
        )

        db.delete(document)
        db.commit()

    except Exception:
        db.rollback()
        raise

    remove_stored_file(stored_filename)
    invalidate_document_cache(owner_id)

    return None
