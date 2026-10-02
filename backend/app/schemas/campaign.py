import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.models.campaign import CampaignStatus


class CampaignICPConfig(BaseModel):
    """Campaign Ideal Customer Profile configuration compatible with AI qualification."""
    industries: List[str] = Field(default_factory=list, description="Target industry verticals")
    geographies: List[str] = Field(default_factory=list, description="Target geographies/countries")
    company_sizes: List[str] = Field(default_factory=list, description="Target company size brackets")
    business_models: List[str] = Field(default_factory=list, description="Target business models")
    technologies: List[str] = Field(default_factory=list, description="Target technologies or stacks")
    target_titles: List[str] = Field(default_factory=list, description="Target buyer/decision-maker titles")
    minimum_score: int = Field(60, ge=0, le=100, description="Minimum ICP score for qualification")

    def to_icp_profile_dict(self) -> Dict[str, Any]:
        """Convert to internal ICPProfile dictionary format for LLM qualification."""
        return {
            "target_industries": self.industries or ["SaaS", "Software", "Tech"],
            "target_company_size": self.company_sizes or ["11-50", "51-200", "201-500", "500+"],
            "target_geographies": self.geographies or ["Global", "North America", "Europe", "India"],
            "required_signals": [
                f"Business model: {', '.join(self.business_models)}" if self.business_models else "B2B focus",
                f"Technologies: {', '.join(self.technologies)}" if self.technologies else "Proprietary software or digital service"
            ],
            "negative_signals": ["Pure consumer B2C marketplace", "Personal blog", "Gambling or adult content"],
            "min_icp_threshold": self.minimum_score,
        }


class CampaignCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    description: Optional[str] = Field(None, description="Campaign description / objectives")
    icp: Optional[Dict[str, Any]] = Field(default_factory=dict, description="ICP criteria")


class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None
    icp: Optional[Dict[str, Any]] = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    icp_config: Dict[str, Any]
    total_leads: int = 0
    qualified_leads: int = 0
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    items: List[CampaignResponse]
    total: int
