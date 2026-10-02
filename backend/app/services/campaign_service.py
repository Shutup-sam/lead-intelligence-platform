import uuid
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from fastapi import HTTPException, status

from app.models.campaign import Campaign, CampaignStatus
from app.models.lead import Lead
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignUpdateRequest,
    CampaignResponse,
    CampaignListResponse,
)

logger = logging.getLogger("lead_intelligence.services.campaign")


class CampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_campaign(
        self, organization_id: uuid.UUID, req: CampaignCreateRequest
    ) -> CampaignResponse:
        campaign = Campaign(
            organization_id=organization_id,
            name=req.name.strip(),
            description=req.description.strip() if req.description else None,
            status=CampaignStatus.ACTIVE.value,
            icp_config=req.icp or {},
        )
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)

        return CampaignResponse(
            id=campaign.id,
            organization_id=campaign.organization_id,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            icp_config=campaign.icp_config,
            total_leads=0,
            qualified_leads=0,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    async def list_campaigns(
        self, organization_id: uuid.UUID
    ) -> CampaignListResponse:
        stmt = (
            select(
                Campaign,
                func.count(Lead.id).label("total_leads"),
                func.count(func.nullif(Lead.icp_score < 50, True)).label("qualified_leads"),
            )
            .outerjoin(Lead, Lead.campaign_id == Campaign.id)
            .where(Campaign.organization_id == organization_id)
            .group_by(Campaign.id)
            .order_by(desc(Campaign.created_at))
        )
        res = await self.db.execute(stmt)
        items = []
        for campaign, total_leads, qualified_leads in res.all():
            items.append(
                CampaignResponse(
                    id=campaign.id,
                    organization_id=campaign.organization_id,
                    name=campaign.name,
                    description=campaign.description,
                    status=campaign.status,
                    icp_config=campaign.icp_config,
                    total_leads=total_leads or 0,
                    qualified_leads=qualified_leads or 0,
                    created_at=campaign.created_at,
                    updated_at=campaign.updated_at,
                )
            )

        return CampaignListResponse(items=items, total=len(items))

    async def get_campaign(
        self, organization_id: uuid.UUID, campaign_id: uuid.UUID
    ) -> CampaignResponse:
        stmt = (
            select(
                Campaign,
                func.count(Lead.id).label("total_leads"),
                func.count(func.nullif(Lead.icp_score < 50, True)).label("qualified_leads"),
            )
            .outerjoin(Lead, Lead.campaign_id == Campaign.id)
            .where(
                Campaign.id == campaign_id,
                Campaign.organization_id == organization_id,
            )
            .group_by(Campaign.id)
        )
        res = await self.db.execute(stmt)
        record = res.first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found.",
            )
        campaign, total_leads, qualified_leads = record
        return CampaignResponse(
            id=campaign.id,
            organization_id=campaign.organization_id,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            icp_config=campaign.icp_config,
            total_leads=total_leads or 0,
            qualified_leads=qualified_leads or 0,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    async def update_campaign(
        self,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        req: CampaignUpdateRequest,
    ) -> CampaignResponse:
        stmt = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == organization_id,
        )
        res = await self.db.execute(stmt)
        campaign = res.scalar_one_or_none()
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found.",
            )

        if req.name is not None:
            campaign.name = req.name.strip()
        if req.description is not None:
            campaign.description = req.description.strip()
        if req.status is not None:
            campaign.status = req.status.value
        if req.icp is not None:
            campaign.icp_config = req.icp

        await self.db.commit()
        await self.db.refresh(campaign)

        # Get counts
        lead_stmt = select(
            func.count(Lead.id),
            func.count(func.nullif(Lead.icp_score < 50, True)),
        ).where(Lead.campaign_id == campaign.id)
        lead_res = await self.db.execute(lead_stmt)
        total_leads, qualified_leads = lead_res.first() or (0, 0)

        return CampaignResponse(
            id=campaign.id,
            organization_id=campaign.organization_id,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            icp_config=campaign.icp_config,
            total_leads=total_leads or 0,
            qualified_leads=qualified_leads or 0,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    async def delete_campaign(
        self, organization_id: uuid.UUID, campaign_id: uuid.UUID
    ) -> None:
        stmt = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == organization_id,
        )
        res = await self.db.execute(stmt)
        campaign = res.scalar_one_or_none()
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found.",
            )

        await self.db.delete(campaign)
        await self.db.commit()
