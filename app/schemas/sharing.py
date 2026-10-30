from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.roles import SharePermission


class ShareCreate(BaseModel):
    recipient_email: str = Field(min_length=3, max_length=255)
    permission: SharePermission = SharePermission.READ


class ShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    shared_with_user_id: int
    shared_by_user_id: int
    permission: str
    created_at: datetime


class SharedDocumentResponse(BaseModel):
    share_id: int
    document_id: int
    original_filename: str
    permission: str
    shared_by_user_id: int
    created_at: datetime


class RoleUpdate(BaseModel):
    role: str
