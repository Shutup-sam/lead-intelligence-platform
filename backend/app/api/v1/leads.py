import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth import require_organization_member
from app.models.organization import Organization
from app.ai.models import LeadQualifyRequest, LeadQualifyResponse
from app.services.lead_service import LeadService
from app.schemas.lead import (
    LeadStatus,
    LeadStatusUpdateRequest,
    LeadListResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    HybridSearchResponse,
)

logger = logging.getLogger("lead_intelligence.api.v1.leads")

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get(
    "",
    response_model=LeadListResponse,
    status_code=status.HTTP_200_OK,
    summary="List qualified leads with pagination and filters",
    description="Returns paginated leads with relational filtering (ICP score range, industry, geography, status, campaign) and search.",
)
async def list_leads(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Free text search across company name, domain, industry, summary"),
    min_icp_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum ICP score filter"),
    max_icp_score: Optional[int] = Query(None, ge=0, le=100, description="Maximum ICP score filter"),
    industry: Optional[str] = Query(None, description="Industry filter"),
    geography: Optional[str] = Query(None, description="Geography/country filter"),
    campaign_id: Optional[uuid.UUID] = Query(None, description="Campaign filter"),
    status_filter: Optional[str] = Query(None, alias="status", description="Lead status (NEW, REVIEW, QUALIFIED, CONTACTED, REJECTED)"),
    sort_by: str = Query("created_at", pattern="^(created_at|icp_score|confidence_score|company_name)$", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction (asc, desc)"),
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> LeadListResponse:
    org, _ = org_tuple
    service = LeadService(db=db)
    return await service.list_leads(
        page=page,
        page_size=page_size,
        search=search,
        min_icp_score=min_icp_score,
        max_icp_score=max_icp_score,
        industry=industry,
        geography=geography,
        status=status_filter,
        organization_id=org.id,
        campaign_id=campaign_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post(
    "/search/semantic",
    response_model=SemanticSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search across leads",
    description="Embeds query into 1536-dimensional vector and performs cosine similarity search on pgvector HNSW index.",
)
async def search_leads_semantic(
    payload: SemanticSearchRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> SemanticSearchResponse:
    org, _ = org_tuple
    service = LeadService(db=db)
    try:
        return await service.semantic_search(
            query=payload.query,
            limit=payload.limit,
            organization_id=org.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Semantic search failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search error: {str(exc)}",
        )


@router.get(
    "/search",
    response_model=HybridSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid search combining semantic similarity, SQL filters, and text matching",
    description="Blends dense vector cosine distance, relational constraints, and keyword matching into an explainable score.",
)
async def search_leads_hybrid(
    q: Optional[str] = Query(None, description="Natural language search or keyword query"),
    min_icp_score: Optional[int] = Query(None, ge=0, le=100),
    max_icp_score: Optional[int] = Query(None, ge=0, le=100),
    industry: Optional[str] = Query(None),
    geography: Optional[str] = Query(None),
    campaign_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(25, ge=1, le=100),
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> HybridSearchResponse:
    org, _ = org_tuple
    service = LeadService(db=db)
    return await service.hybrid_search(
        query=q,
        min_icp_score=min_icp_score,
        max_icp_score=max_icp_score,
        industry=industry,
        geography=geography,
        status=status_filter,
        organization_id=org.id,
        campaign_id=campaign_id,
        limit=limit,
    )


@router.get(
    "/export.csv",
    summary="Export leads to CSV",
    description="Generates a downloadable CSV with sales-intelligence fields based on current filter parameters.",
)
async def export_leads_csv(
    search: Optional[str] = Query(None),
    min_icp_score: Optional[int] = Query(None, ge=0, le=100),
    max_icp_score: Optional[int] = Query(None, ge=0, le=100),
    industry: Optional[str] = Query(None),
    geography: Optional[str] = Query(None),
    campaign_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_tuple
    service = LeadService(db=db)
    csv_content = await service.export_leads(
        format_type="csv",
        search=search,
        min_icp_score=min_icp_score,
        max_icp_score=max_icp_score,
        industry=industry,
        geography=geography,
        status=status_filter,
        organization_id=org.id,
        campaign_id=campaign_id,
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )


@router.get(
    "/export.json",
    summary="Export leads to JSON",
    description="Generates a downloadable JSON file based on current filter parameters.",
)
async def export_leads_json(
    search: Optional[str] = Query(None),
    min_icp_score: Optional[int] = Query(None, ge=0, le=100),
    max_icp_score: Optional[int] = Query(None, ge=0, le=100),
    industry: Optional[str] = Query(None),
    geography: Optional[str] = Query(None),
    campaign_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_tuple
    service = LeadService(db=db)
    json_data = await service.export_leads(
        format_type="json",
        search=search,
        min_icp_score=min_icp_score,
        max_icp_score=max_icp_score,
        industry=industry,
        geography=geography,
        status=status_filter,
        organization_id=org.id,
        campaign_id=campaign_id,
    )
    return Response(
        content=json.dumps(json_data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=leads_export.json"},
    )


@router.post(
    "/seed-demo",
    status_code=status.HTTP_200_OK,
    summary="Seed synthetic demo leads for development & testing",
    description="Creates 6 realistic, clearly labelled demo leads with full signals, embeddings, and source pages.",
)
async def seed_demo_leads(
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    org, _ = org_tuple
    service = LeadService(db=db)
    try:
        lead_ids = await service.seed_demo_leads(organization_id=org.id)
        return {
            "message": f"Successfully seeded {len(lead_ids)} demo leads.",
            "count": len(lead_ids),
            "lead_ids": lead_ids,
        }
    except Exception as exc:
        logger.error("Demo seeding failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Seed error: {str(exc)}",
        )


@router.post(
    "/qualify/{crawl_target_id}",
    response_model=LeadQualifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Qualify a crawled business domain against ICP criteria",
    description="Loads crawled website pages, executes LLM qualification with strict schema validation, extracts signals, generates dense pgvector embeddings, and persists the lead.",
)
async def qualify_lead(
    crawl_target_id: uuid.UUID,
    payload: Optional[LeadQualifyRequest] = None,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> LeadQualifyResponse:
    org, _ = org_tuple
    service = LeadService(db=db)
    icp_profile = payload.icp_profile if payload else None

    try:
        result = await service.qualify_target(
            crawl_target_id=crawl_target_id,
            icp_profile=icp_profile,
            organization_id=org.id,
        )
        return result
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except Exception as exc:
        logger.error("Lead qualification failed for target %s: %s", crawl_target_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lead qualification pipeline failure: {str(exc)}",
        )


@router.patch(
    "/{lead_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Update lead workflow status",
    description="Updates the lead status to one of: NEW, REVIEW, QUALIFIED, CONTACTED, REJECTED.",
)
async def update_lead_status(
    lead_id: uuid.UUID,
    payload: LeadStatusUpdateRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    org, _ = org_tuple
    service = LeadService(db=db)
    try:
        updated = await service.update_lead_status(lead_id, payload.status.value, organization_id=org.id)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with ID '{lead_id}' not found.",
            )
        return {
            "lead_id": str(updated.id),
            "status": updated.status,
            "updated_at": updated.updated_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{lead_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve qualified lead details",
    description="Fetches full lead intelligence, traceable qualification signals, source pages, embedding metadata, and LLM telemetry.",
)
async def get_lead_details(
    lead_id: uuid.UUID,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    org, _ = org_tuple
    service = LeadService(db=db)
    lead = await service.get_lead(lead_id, organization_id=org.id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID '{lead_id}' not found.",
        )
    return lead
