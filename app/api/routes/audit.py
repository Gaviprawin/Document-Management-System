from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.rbac import AdminUser
from app.models.audit_log import AuditLog

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin Audit Logs"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/audit-logs")
def list_audit_logs(
    current_user: AdminUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "ip_address": item.ip_address,
            "details": item.details,
            "created_at": item.created_at,
        }
        for item in logs
    ]