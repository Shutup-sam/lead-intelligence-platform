import uuid
import logging
from typing import Tuple
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import require_organization_member
from app.models.organization import Organization
from app.services.campaign_service import CampaignService
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignUpdateRequest,
    CampaignResponse,
    CampaignListResponse,
)

logger = logging.getLogger("lead_intelligence.api.campaigns")

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    req: CampaignCreateRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a new campaign with target ICP configuration scoped to the active organization."""
    org, _ = org_tuple
    service = CampaignService(db)
    return await service.create_campaign(org.id, req)


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """List all campaigns belonging to the active organization."""
    org, _ = org_tuple
    service = CampaignService(db)
    return await service.list_campaigns(org.id)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details for a specific campaign belonging to the active organization."""
    org, _ = org_tuple
    service = CampaignService(db)
    return await service.get_campaign(org.id, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    req: CampaignUpdateRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """Update campaign metadata, status, or ICP criteria."""
    org, _ = org_tuple
    service = CampaignService(db)
    return await service.update_campaign(org.id, campaign_id, req)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: uuid.UUID,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """Delete a campaign belonging to the active organization."""
    org, _ = org_tuple
    service = CampaignService(db)
    await service.delete_campaign(org.id, campaign_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
