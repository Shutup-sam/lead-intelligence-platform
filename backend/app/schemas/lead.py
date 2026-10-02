import uuid
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class LeadStatus(str, Enum):
    NEW = "NEW"
    REVIEW = "REVIEW"
    QUALIFIED = "QUALIFIED"
    CONTACTED = "CONTACTED"
    REJECTED = "REJECTED"


class LeadStatusUpdateRequest(BaseModel):
    status: LeadStatus


class LeadListItem(BaseModel):
    lead_id: str
    crawl_target_id: str
    company_name: str
    domain: str
    industry: str
    company_summary: str
    value_proposition: str
    icp_score: int
    confidence_score: float
    geography: str
    estimated_company_size: str
    status: str
    created_at: str
    similarity: Optional[float] = None


class LeadListResponse(BaseModel):
    items: List[LeadListItem]
    page: int
    page_size: int
    total: int
    pages: int


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000, description="Natural language search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of leads to return")


class SemanticSearchResultItem(BaseModel):
    lead_id: str
    company_name: str
    domain: str
    industry: str
    company_summary: str
    icp_score: int
    confidence_score: float
    geography: str
    status: str
    similarity: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: List[SemanticSearchResultItem]
    count: int


class HybridSearchResponse(BaseModel):
    query: Optional[str] = None
    results: List[LeadListItem]
    total: int
    ranking_strategy: str


class SourcePageItem(BaseModel):
    id: str
    url: str
    final_url: str
    title: Optional[str] = None
    depth: int
    status_code: int
    fetched_at: str


class SignalItem(BaseModel):
    id: str
    signal: str
    evidence: str
    source_url: Optional[str] = None
    sentiment: str
    created_at: str


class AuditLogItem(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    request_id: Optional[str] = None
    created_at: str


class EmbeddingMetadataItem(BaseModel):
    id: str
    content_hash: str
    dimension: int
    indexed_hnsw: bool
    created_at: str


class LeadDetailResponse(BaseModel):
    id: str
    crawl_target_id: str
    company_name: str
    domain: str
    company_summary: str
    value_proposition: str
    industry: str
    target_audience: str
    business_model: str
    geography: str
    estimated_company_size: str
    technology_signals: List[str]
    icp_score: int
    confidence_score: float
    status: str
    qualification_reasoning: str
    qualification_json: Dict[str, Any]
    created_at: str
    updated_at: str
    positive_signals: List[str]
    negative_signals: List[str]
    signals: List[SignalItem]
    source_pages: List[SourcePageItem]
    embedding: Optional[EmbeddingMetadataItem] = None
    audit_logs: List[AuditLogItem]
