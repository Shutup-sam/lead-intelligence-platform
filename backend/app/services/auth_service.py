import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.user import User
from app.models.organization import Organization, OrganizationMember, OrganizationRole
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    OrganizationResponse,
    CurrentUserResponse,
)

logger = logging.getLogger("lead_intelligence.services.auth")


def slugify(text: str) -> str:
    """Create a URL-friendly slug from a string."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "workspace"


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, req: UserRegisterRequest) -> TokenResponse:
        # 1. Check if email already registered
        existing_stmt = select(User).where(User.email == req.email.lower().strip())
        res = await self.db.execute(existing_stmt)
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists.",
            )

        # 2. Hash password & create User
        pwd_hash = hash_password(req.password)
        user = User(
            email=req.email.lower().strip(),
            password_hash=pwd_hash,
            full_name=req.full_name.strip(),
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()

        # 3. Create Default Organization
        org_name = (req.organization_name or f"{req.full_name}'s Workspace").strip()
        base_slug = slugify(org_name)
        # Ensure unique slug
        slug = base_slug
        counter = 1
        while True:
            slug_stmt = select(Organization).where(Organization.slug == slug)
            slug_res = await self.db.execute(slug_stmt)
            if not slug_res.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        org = Organization(
            name=org_name,
            slug=slug,
        )
        self.db.add(org)
        await self.db.flush()

        # 4. Associate as OWNER
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=OrganizationRole.OWNER.value,
        )
        self.db.add(member)
        await self.db.commit()

        # 5. Generate Token
        token = create_access_token({
            "sub": str(user.id),
            "org_id": str(org.id),
        })

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at,
            ),
            organization=OrganizationResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                role=OrganizationRole.OWNER.value,
                created_at=org.created_at,
            ),
        )

    async def login(self, req: UserLoginRequest) -> TokenResponse:
        # 1. Fetch user by email
        stmt = select(User).where(User.email == req.email.lower().strip())
        res = await self.db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Contact support.",
            )

        # 2. Fetch user's primary organization membership
        mem_stmt = (
            select(OrganizationMember, Organization)
            .join(Organization, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user.id)
            .order_by(OrganizationMember.created_at.asc())
        )
        mem_res = await self.db.execute(mem_stmt)
        primary_mem = mem_res.first()

        if not primary_mem:
            # If for some reason user has no organization, create a personal workspace
            org_name = f"{user.full_name}'s Workspace"
            slug = slugify(f"{user.full_name}-{uuid.uuid4().hex[:6]}")
            org = Organization(name=org_name, slug=slug)
            self.db.add(org)
            await self.db.flush()
            mem = OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role=OrganizationRole.OWNER.value,
            )
            self.db.add(mem)
            await self.db.commit()
            org_id = org.id
            org_model = org
            role = OrganizationRole.OWNER.value
        else:
            member_obj, org_model = primary_mem
            org_id = org_model.id
            role = member_obj.role

        token = create_access_token({
            "sub": str(user.id),
            "org_id": str(org_id),
        })

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at,
            ),
            organization=OrganizationResponse(
                id=org_model.id,
                name=org_model.name,
                slug=org_model.slug,
                role=role,
                created_at=org_model.created_at,
            ),
        )

    async def get_current_user_profile(
        self, user: User, current_org: Organization, current_role: str
    ) -> CurrentUserResponse:
        # Fetch all organizations user belongs to
        stmt = (
            select(OrganizationMember, Organization)
            .join(Organization, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user.id)
            .order_by(OrganizationMember.created_at.asc())
        )
        res = await self.db.execute(stmt)
        org_responses = [
            OrganizationResponse(
                id=o.id,
                name=o.name,
                slug=o.slug,
                role=m.role,
                created_at=o.created_at,
            )
            for m, o in res.all()
        ]

        return CurrentUserResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at,
            ),
            organization=OrganizationResponse(
                id=current_org.id,
                name=current_org.name,
                slug=current_org.slug,
                role=current_role,
                created_at=current_org.created_at,
            ),
            organizations=org_responses,
        )
