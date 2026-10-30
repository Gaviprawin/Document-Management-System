
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.audit import record_audit
from app.services.auth import authenticate_user, register_user

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    db: DbSession,
):
    try:
        return register_user(db, user_data)

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/login",
    response_model=TokenResponse,
)
@limiter.limit("20/minute")
def login(
    request: Request,
    login_data: LoginRequest,
    db: DbSession,
):
    user = authenticate_user(
        db,
        login_data.email,
        login_data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        record_audit(
            db=db,
            user_id=user.id,
            action="auth.login",
            resource_type="user",
            resource_id=str(user.id),
            ip_address=(
                request.client.host if request.client else None
            ),
            details={"email": user.email},
        )

        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise

    access_token = create_access_token(user.id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_my_profile(
    current_user: CurrentUser,
):
    return current_user
