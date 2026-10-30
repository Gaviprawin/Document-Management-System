
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.roles import SharePermission, UserRole
from app.db.session import get_db
from app.models.document import Document
from app.models.document_share import DocumentShare
from app.models.user import User
from app.schemas.sharing import (
    ShareCreate,
    ShareResponse,
    SharedDocumentResponse,
)
from app.services.audit import record_audit
from app.services.permissions import (
    ensure_document_access,
    get_document_or_404,
)

router = APIRouter(
    prefix="/api/v1/shares",
    tags=["Document Sharing"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def commit_with_rollback(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


@router.post(
    "/documents/{document_id}",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
)
def share_document(
    document_id: int,
    share_data: ShareCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    document = get_document_or_404(db, document_id)

    ensure_document_access(
        db,
        document,
        current_user,
        action="share",
    )

    recipient = db.scalar(
        select(User).where(
            User.email == share_data.recipient_email
        )
    )

    if recipient is None:
        raise HTTPException(
            status_code=404,
            detail="Recipient user not found",
        )

    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot share a document with yourself",
        )

    permission = getattr(
        share_data.permission,
        "value",
        share_data.permission,
    )

    allowed_permissions = {
        item.value for item in SharePermission
    }

    if permission not in allowed_permissions:
        raise HTTPException(
            status_code=400,
            detail="Invalid sharing permission",
        )

    share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == recipient.id,
        )
    )

    if share is None:
        share = DocumentShare(
            document_id=document_id,
            shared_with_user_id=recipient.id,
            shared_by_user_id=current_user.id,
            permission=permission,
        )
        db.add(share)
        action = "document.share"
    else:
        share.permission = permission
        share.shared_by_user_id = current_user.id
        action = "document.share.update"

    try:
        db.flush()

        record_audit(
            db=db,
            user_id=current_user.id,
            action=action,
            resource_type="document",
            resource_id=str(document_id),
            ip_address=get_client_ip(request),
            details={
                "recipient_id": recipient.id,
                "permission": permission,
            },
        )

        commit_with_rollback(db)
        db.refresh(share)

    except Exception:
        db.rollback()
        raise

    return share


@router.get(
    "/received",
    response_model=list[SharedDocumentResponse],
)
def get_received_shares(
    db: DbSession,
    current_user: CurrentUser,
):
    results = (
        db.query(DocumentShare, Document)
        .join(
            Document,
            DocumentShare.document_id == Document.id,
        )
        .filter(
            DocumentShare.shared_with_user_id == current_user.id
        )
        .order_by(DocumentShare.id.desc())
        .all()
    )

    response = []

    for share, document in results:
        share_created_at = getattr(share, "created_at", None)

        if share_created_at is None:
            share_created_at = document.created_at

        response.append(
            {
                "share_id": share.id,
                "document_id": document.id,
                "original_filename": document.original_filename,
                "permission": getattr(
                    share.permission,
                    "value",
                    share.permission,
                ),
                "created_at": share_created_at,
                "shared_by_user_id": share.shared_by_user_id,
            }
        )

    return response


@router.delete(
    "/documents/{document_id}/users/{recipient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_document_share(
    document_id: int,
    recipient_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    document = get_document_or_404(db, document_id)

    role = getattr(current_user, "role", UserRole.USER.value)
    role = getattr(role, "value", role)

    if (
        role != UserRole.ADMIN.value
        and document.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document owner or an admin can revoke sharing",
        )

    share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == recipient_id,
        )
    )

    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document share not found",
        )

    try:
        record_audit(
            db=db,
            user_id=current_user.id,
            action="document.share.revoke",
            resource_type="document",
            resource_id=str(document_id),
            ip_address=get_client_ip(request),
            details={"recipient_id": recipient_id},
        )

        db.delete(share)
        commit_with_rollback(db)

    except Exception:
        db.rollback()
        raise

    return None
