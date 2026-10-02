from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GroundedField(BaseModel):
    """Traceable status for a specific company attribute (observed, inferred, or unknown)."""
    value: Optional[str] = Field(None, description="Extracted value or 'Unknown'")
    status: str = Field("unknown", description="'observed' (directly stated), 'inferred' (deduced from clues), or 'unknown' (no evidence)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    evidence: Optional[str] = Field(None, description="Direct quote or specific reasoning from crawled text")
    source_url: Optional[str] = Field(None, description="Source page URL where evidence was found")


class QualificationSignal(BaseModel):
    """Traceable, evidence-backed conclusion tied to a specific source page URL."""
    signal: str = Field(..., description="Summary of the signal (e.g. 'B2B Enterprise SaaS offering')")
    evidence: str = Field(..., description="Direct factual quote or concrete evidence from the website")
    source_url: Optional[str] = Field(None, description="Source page URL where evidence was found")
    sentiment: str = Field("positive", description="'positive', 'negative', or 'neutral'")
    status: str = Field("observed", description="'observed' (direct quote), 'inferred' (deduced with reasoning), or 'unknown'")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence in this signal")


class CompanyQualification(BaseModel):
    """Strict structured Pydantic schema returned by LLM qualification with strict evidence grounding."""
    company_name: str = Field(..., description="Official trading name of the company or domain")
    company_summary: str = Field(..., description="2-3 sentence overview of what the company or site is based strictly on crawled content")
    value_proposition: str = Field(..., description="Core value proposition, or 'Unknown / None' if non-commercial or unstated")
    industry: str = Field(..., description="Primary industry vertical, or 'Unknown'")
    target_audience: str = Field(..., description="Target customer profile, or 'Unknown' if not stated")
    products_or_services: List[str] = Field(default_factory=list, description="Explicitly verified products/services, or empty list if none")
    business_model: str = Field(..., description="e.g. 'B2B Subscription', or 'Unknown', or 'Non-Commercial / Sandbox'")
    geography: str = Field(..., description="Operating regions or headquarters, or 'Unknown'")
    estimated_company_size: str = Field(..., description="Headcount bracket ('1-10', '11-50', '51-200', '201-500', '500+'), or 'Unknown'")
    technology_signals: List[str] = Field(default_factory=list, description="Technologies explicitly named in crawled text/metadata, or empty list")
    contact_signals: Dict[str, Any] = Field(default_factory=dict, description="Contact information, emails, locations verified")

    # Qualification scoring (enforces strict 0-100 and 0.0-1.0 boundaries)
    icp_score: int = Field(..., ge=0, le=100, description="Ideal Customer Profile fit score between 0 and 100")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")

    positive_signals: List[str] = Field(default_factory=list, description="Key bullet points supporting qualification")
    negative_signals: List[str] = Field(default_factory=list, description="Disqualifying factors or missing criteria")
    qualification_reasoning: str = Field(..., description="Detailed paragraph explaining why this score was assigned based strictly on evidence")

    # Traceable evidence signals
    signals: List[QualificationSignal] = Field(
        default_factory=list,
        description="Granular, evidence-backed qualification signals tied to source URLs"
    )

    # Explicit Grounding Breakdown (Separating Facts, Inferences, Unknowns)
    observed_facts: List[str] = Field(
        default_factory=list,
        description="Directly observed, verifiable facts with page citations"
    )
    inferred_signals: List[str] = Field(
        default_factory=list,
        description="Plausible inferences derived from clues, with reasoning and confidence"
    )
    unknown_attributes: List[str] = Field(
        default_factory=list,
        description="Explicit list of company attributes where evidence was completely absent in crawled pages"
    )
    grounded_attributes: Dict[str, GroundedField] = Field(
        default_factory=dict,
        description="Detailed grounding status for company attributes (company_size, business_model, products, etc.)"
    )


class ICPProfile(BaseModel):
    """Configurable Ideal Customer Profile criteria used to evaluate candidates."""
    target_industries: List[str] = Field(
        default_factory=lambda: ["SaaS", "Enterprise Software", "Logistics Tech", "Supply Chain", "Fintech", "E-Commerce Tech"],
        description="Preferred industry sectors"
    )
    target_company_size: List[str] = Field(
        default_factory=lambda: ["11-50", "51-200", "201-500", "500+"],
        description="Target team/company headcount brackets"
    )
    target_geographies: List[str] = Field(
        default_factory=lambda: ["Global", "North America", "United States", "Europe", "India"],
        description="Target operating or headquarters regions"
    )
    required_signals: List[str] = Field(
        default_factory=lambda: ["B2B focus", "Proprietary software or digital service offering"],
        description="Mandatory traits for high qualification"
    )
    negative_signals: List[str] = Field(
        default_factory=lambda: ["Pure consumer B2C marketplace", "Personal hobby blog", "Gambling or adult content"],
        description="Automatic disqualifiers"
    )
    min_icp_threshold: int = Field(50, ge=0, le=100, description="Threshold above which lead is considered qualified")


class LeadQualifyRequest(BaseModel):
    """Request payload for qualifying a crawled target."""
    icp_profile: Optional[ICPProfile] = None


class LeadQualifyResponse(BaseModel):
    """Structured response for lead qualification."""
    lead_id: str
    company_name: str
    domain: str
    icp_score: int
    confidence_score: float
    signals_count: int
    embedding_created: bool
    llm_provider: str
    llm_model: str
    duration_seconds: float
