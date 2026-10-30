
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import UserRole
from app.models.document import Document
from app.models.document_share import DocumentShare
from app.models.user import User


def get_document_or_404(
    db: Session,
    document_id: int,
) -> Document:
    document = db.scalar(
        select(Document).where(Document.id == document_id)
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


def ensure_document_access(
    db: Session,
    document: Document,
    user: User,
    action: str = "read",
) -> Document:
    role = getattr(user, "role", UserRole.USER.value)
    role = getattr(role, "value", role)

    # Administrators can perform all actions.
    if role == UserRole.ADMIN.value:
        return document

    # Managers can read and download documents.
    if role == UserRole.MANAGER.value and action in {
        "read",
        "download",
    }:
        return document

    # Document owners can manage their own documents.
    if document.owner_id == user.id:
        if action in {
            "read",
            "download",
            "delete",
            "share",
        }:
            return document

    # Other users require an explicit sharing permission.
    share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == document.id,
            DocumentShare.shared_with_user_id == user.id,
        )
    )

    if share is not None:
        permission = getattr(share.permission, "value", share.permission)

        if action == "read" and permission in {"read", "download"}:
            return document

        if action == "download" and permission == "download":
            return document

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this document",
    )
