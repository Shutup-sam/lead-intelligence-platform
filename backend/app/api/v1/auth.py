import logging
from typing import Tuple
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.services.auth_service import AuthService
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    CurrentUserResponse,
)

logger = logging.getLogger("lead_intelligence.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account, initialize their default organization, and return session token."""
    service = AuthService(db)
    return await service.register(req)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password and return access token."""
    service = AuthService(db)
    return await service.login(req)


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
):
    """Stateless JWT logout endpoint."""
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    org_tuple: Tuple[Organization, str] = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Return profile details, active organization, and organization memberships."""
    current_org, role = org_tuple
    service = AuthService(db)
    return await service.get_current_user_profile(current_user, current_org, role)
