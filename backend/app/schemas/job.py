import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.models.job import JobType, JobStatus
from app.ai.models import ICPProfile


class JobEnqueueCrawlRequest(BaseModel):
    url: str = Field(..., description="Target website URL to crawl")
    max_pages: int = Field(default=6, ge=1, le=20, description="Max pages to crawl")
    campaign_id: Optional[uuid.UUID] = Field(default=None, description="Associated Campaign ID")
    force: bool = Field(default=False, description="Force new crawl even if an active job exists")


class JobEnqueueQualifyRequest(BaseModel):
    crawl_target_id: uuid.UUID = Field(..., description="UUID of existing CrawlTarget")
    campaign_id: Optional[uuid.UUID] = Field(default=None, description="Associated Campaign ID")
    icp_profile: Optional[ICPProfile] = Field(default=None, description="Custom ICP criteria")
    force: bool = Field(default=False, description="Force new qualification even if an active job exists")


class JobEnqueuePipelineRequest(BaseModel):
    url: str = Field(..., description="Target website URL to crawl and qualify in one pipeline")
    max_pages: int = Field(default=6, ge=1, le=20, description="Max pages to crawl")
    campaign_id: Optional[uuid.UUID] = Field(default=None, description="Associated Campaign ID")
    icp_profile: Optional[ICPProfile] = Field(default=None, description="Custom ICP criteria")
    force: bool = Field(default=False, description="Force new pipeline job even if an active job exists")


class JobEnqueueResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    message: str
    reused: bool = False


class JobStatusResponse(BaseModel):
    id: str
    job_type: str
    status: str
    progress: int
    current_stage: str
    pages_discovered: int
    pages_crawled: int
    organization_id: Optional[str] = None
    campaign_id: Optional[str] = None
    crawl_target_id: Optional[str] = None
    lead_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    payload: Dict[str, Any]
    result: Dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class JobCancelResponse(BaseModel):
    job_id: str
    status: str
    message: str
