from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.roles import UserRole
from app.models.user import User


def require_roles(*allowed_roles: UserRole) -> Callable:
    allowed_values = {role.value for role in allowed_roles}

    def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_role = getattr(current_user, "role", None)

        if user_role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return role_checker


AdminUser = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN)),
]

ManagerUser = Annotated[
    User,
    Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
]

StaffUser = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MANAGER,
            UserRole.USER,
        )
    ),
]
