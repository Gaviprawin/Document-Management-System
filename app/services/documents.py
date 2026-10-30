
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.user import User


STORAGE_DIR = Path(settings.DOCUMENT_STORAGE_DIR).resolve()

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_TYPES = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
}


def validate_file(filename: str, content_type: str):
    safe_name = Path(filename.replace("\\", "/")).name
    extension = Path(safe_name).suffix.lower()

    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(400, "Invalid filename")

    if len(safe_name) > 255:
        raise HTTPException(
            400,
            "Filename must be 255 characters or fewer",
        )

    if extension not in ALLOWED_TYPES:
        raise HTTPException(
            415,
            "Unsupported file extension. Allowed: PDF, TXT, PNG, JPG, JPEG",
        )

    expected_types = ALLOWED_TYPES[extension]

    if content_type not in expected_types:
        raise HTTPException(
            415,
            "File extension and content type do not match",
        )

    return safe_name, extension


def validate_file_content(extension: str, content: bytes):
    if not content:
        raise HTTPException(
            400,
            "Empty files are not allowed",
        )

    if extension == ".pdf":
        valid = content.startswith(b"%PDF-")

    elif extension == ".png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")

    elif extension in {".jpg", ".jpeg"}:
        valid = content.startswith(b"\xff\xd8\xff")

    elif extension == ".txt":
        try:
            content.decode("utf-8")
            valid = True
        except UnicodeDecodeError:
            valid = False

    else:
        valid = False

    if not valid:
        raise HTTPException(
            415,
            "File content does not match the declared file type",
        )


def get_owned_document(
    db: Session,
    document_id: int,
    current_user: User,
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return document


async def save_document(
    db: Session,
    upload: UploadFile,
    current_user: User,
) -> Document:
    original_name, extension = validate_file(
        upload.filename or "",
        upload.content_type or "",
    )

    file_path = None

    try:
        content = await upload.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB",
            )

        validate_file_content(extension, content)

        stored_filename = f"{uuid4().hex}{extension}"

        STORAGE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path = (STORAGE_DIR / stored_filename).resolve()

        if file_path.parent != STORAGE_DIR:
            raise HTTPException(
                status_code=400,
                detail="Invalid storage path",
            )

        with file_path.open("xb") as file:
            file.write(content)

        document = Document(
            owner_id=current_user.id,
            original_filename=original_name,
            stored_filename=stored_filename,
            content_type=upload.content_type or "",
            size_bytes=len(content),
        )

        db.add(document)

        # Assign the database ID without committing the transaction.
        # The API route commits the document and audit log together.
        db.flush()
        db.refresh(document)

        return document

    except Exception:
        db.rollback()

        if file_path is not None:
            file_path.unlink(missing_ok=True)

        raise

    finally:
        await upload.close()


def list_documents(
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    search: str | None,
    content_type: str | None,
    sort_by: str,
    order: str,
):
    filters = [
        Document.owner_id == current_user.id,
    ]

    if search:
        escaped_search = (
            search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        filters.append(
            Document.original_filename.ilike(
                f"%{escaped_search}%",
                escape="\\",
            )
        )

    if content_type:
        filters.append(
            Document.content_type == content_type,
        )

    total = db.scalar(
        select(func.count(Document.id)).where(*filters)
    ) or 0

    sortable_columns = {
        "created_at": Document.created_at,
        "filename": Document.original_filename,
        "size": Document.size_bytes,
    }

    column = sortable_columns[sort_by]

    if order == "desc":
        column = column.desc()
    else:
        column = column.asc()

    items = db.scalars(
        select(Document)
        .where(*filters)
        .order_by(column, Document.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def delete_document_file(document: Document):
    file_path = (
        STORAGE_DIR / document.stored_filename
    ).resolve()

    if file_path.parent != STORAGE_DIR:
        raise HTTPException(
            status_code=400,
            detail="Invalid storage path",
        )

    file_path.unlink(missing_ok=True)
