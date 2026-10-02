import uuid
import logging
from typing import Optional, Tuple
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.organization import Organization, OrganizationMember, OrganizationRole

logger = logging.getLogger("lead_intelligence.auth")

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and authenticate the user from the Bearer JWT token or query parameter."""
    raw_token = credentials.credentials if credentials and credentials.credentials else token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


async def get_current_organization(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    org_id: Optional[str] = None,
) -> Tuple[Organization, str]:
    """
    Returns the active (Organization, role) tuple for the authenticated user.
    If X-Organization-Id header or org_id query parameter is supplied, validates that user belongs to that organization.
    Otherwise, defaults to the user's primary/first organization.
    """
    effective_org_id = x_organization_id or org_id
    if effective_org_id:
        try:
            target_org_id = uuid.UUID(effective_org_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization ID UUID format.",
            )

        stmt = (
            select(OrganizationMember, Organization)
            .join(Organization, OrganizationMember.organization_id == Organization.id)
            .where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == target_org_id,
            )
        )
        res = await db.execute(stmt)
        record = res.first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organization.",
            )
        member_obj, org_obj = record
        return org_obj, member_obj.role

    # Default to user's first organization
    stmt = (
        select(OrganizationMember, Organization)
        .join(Organization, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(OrganizationMember.created_at.asc())
    )
    res = await db.execute(stmt)
    record = res.first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any organization.",
        )
    member_obj, org_obj = record
    return org_obj, member_obj.role


async def require_organization_member(
    org_tuple: Tuple[Organization, str] = Depends(get_current_organization),
) -> Tuple[Organization, str]:
    """Ensures user is at least a MEMBER of the active organization."""
    return org_tuple


async def require_organization_owner(
    org_tuple: Tuple[Organization, str] = Depends(get_current_organization),
) -> Tuple[Organization, str]:
    """Ensures user is an OWNER of the active organization."""
    org, role = org_tuple
    if role != OrganizationRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action requires organization OWNER role.",
        )
    return org, role
