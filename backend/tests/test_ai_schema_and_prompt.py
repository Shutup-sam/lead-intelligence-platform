import pytest
from pydantic import ValidationError
from app.ai.models import CompanyQualification, QualificationSignal, ICPProfile
from app.ai.prompt import build_qualification_user_prompt, SYSTEM_PROMPT


def test_valid_company_qualification_schema():
    valid_data = {
        "company_name": "Apex Logic",
        "company_summary": "Apex Logic delivers automated sales workflows.",
        "value_proposition": "Cut sales cycle duration by 40% using AI.",
        "industry": "B2B SaaS",
        "target_audience": "Mid-market software sales teams",
        "products_or_services": ["Sales Copilot", "Pipeline Intelligence API"],
        "business_model": "B2B SaaS Subscription",
        "geography": "United States",
        "estimated_company_size": "51-200",
        "technology_signals": ["PostgreSQL", "React", "Python"],
        "contact_signals": {"emails": ["hello@apexlogic.io"]},
        "icp_score": 85,
        "confidence_score": 0.92,
        "positive_signals": ["B2B SaaS model", "Target company size"],
        "negative_signals": [],
        "qualification_reasoning": "Strong match with target criteria.",
        "signals": [
            {
                "signal": "B2B SaaS model",
                "evidence": "Pricing plans offered as monthly SaaS subscription.",
                "source_url": "https://apexlogic.io/pricing",
                "sentiment": "positive",
            }
        ],
    }

    qual = CompanyQualification.model_validate(valid_data)
    assert qual.company_name == "Apex Logic"
    assert qual.icp_score == 85
    assert qual.confidence_score == 0.92
    assert len(qual.signals) == 1
    assert qual.signals[0].signal == "B2B SaaS model"


def test_invalid_icp_score_boundaries():
    base_data = {
        "company_name": "Apex Logic",
        "company_summary": "Apex Logic summary",
        "value_proposition": "Value prop",
        "industry": "B2B SaaS",
        "target_audience": "Target audience",
        "business_model": "SaaS",
        "geography": "US",
        "estimated_company_size": "11-50",
        "qualification_reasoning": "Reasoning",
        "confidence_score": 0.8,
    }

    # Score > 100 must fail validation
    with pytest.raises(ValidationError):
        CompanyQualification.model_validate({**base_data, "icp_score": 105})

    # Score < 0 must fail validation
    with pytest.raises(ValidationError):
        CompanyQualification.model_validate({**base_data, "icp_score": -5})


def test_invalid_confidence_score_boundaries():
    base_data = {
        "company_name": "Apex Logic",
        "company_summary": "Apex Logic summary",
        "value_proposition": "Value prop",
        "industry": "B2B SaaS",
        "target_audience": "Target audience",
        "business_model": "SaaS",
        "geography": "US",
        "estimated_company_size": "11-50",
        "qualification_reasoning": "Reasoning",
        "icp_score": 75,
    }

    # Confidence > 1.0 must fail validation
    with pytest.raises(ValidationError):
        CompanyQualification.model_validate({**base_data, "confidence_score": 1.5})

    # Confidence < 0.0 must fail validation
    with pytest.raises(ValidationError):
        CompanyQualification.model_validate({**base_data, "confidence_score": -0.1})


def test_qualification_prompt_structure_and_criteria():
    icp = ICPProfile(
        target_industries=["Fintech", "Logistics"],
        target_company_size=["51-200"],
        required_signals=["API-first architecture"],
        negative_signals=["Gambling"],
        min_icp_threshold=60,
    )

    pages = [
        {
            "url": "https://apexlogic.io/about",
            "title": "About Apex Logic",
            "content_markdown": "Apex Logic builds API-first logistics infrastructure.",
            "metadata": {"emails": ["info@apexlogic.io"]},
        }
    ]

    prompt = build_qualification_user_prompt(
        domain="apexlogic.io",
        target_url="https://apexlogic.io/",
        pages_data=pages,
        icp_profile=icp,
    )

    # Required instructions and sections exist
    assert "apexlogic.io" in prompt
    assert "Fintech" in prompt
    assert "Logistics" in prompt
    assert "API-first architecture" in prompt
    assert "Gambling" in prompt
    assert "info@apexlogic.io" in prompt
    assert "REQUIRED JSON OUTPUT FORMAT" in prompt

    # System prompt requirements
    assert "EVIDENCE-BASED ONLY" in SYSTEM_PROMPT
    assert "PRECISE SCORING (0-100)" in SYSTEM_PROMPT
    assert "CONFIDENCE SCORE (0.0 - 1.0)" in SYSTEM_PROMPT
