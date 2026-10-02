import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import HTTPException
from app.main import app
from app.core.auth import (
    get_current_user,
    get_current_organization,
    require_organization_member,
    require_organization_owner,
)
from app.core.database import get_db
from app.services.campaign_service import CampaignService
from app.services.job_service import JobService
from app.schemas.campaign import CampaignCreateRequest, CampaignICPConfig
from app.models.organization import Organization
from app.models.job import Job, JobType, JobStatus


@pytest.mark.asyncio
async def test_auth_register_and_login_flow(client: AsyncClient):
    """Test full registration and login lifecycle with default org assignment."""
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"

    # 1. Register new user
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Test Founder",
            "organization_name": "Acme Innovations",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == unique_email
    assert reg_data["user"]["full_name"] == "Test Founder"
    assert reg_data["organization"]["name"] == "Acme Innovations"
    assert reg_data["organization"]["role"] == "OWNER"

    # 2. Duplicate registration should be rejected
    dup_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "AnotherPassword456!",
            "full_name": "Duplicate User",
        },
    )
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["detail"]

    # 3. Login with correct credentials
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_email,
            "password": "SecurePassword123!",
        },
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    assert login_data["user"]["email"] == unique_email

    # 4. Login with incorrect password
    bad_login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_email,
            "password": "WrongPassword999!",
        },
    )
    assert bad_login_resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_access_rejected():
    """Verify that protected endpoints reject requests when no or invalid credentials are provided."""
    # Temporarily remove dependency overrides to test actual security dependencies
    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as raw_client:
            # 1. No Authorization header -> 401
            resp_no_auth = await raw_client.get("/api/v1/auth/me")
            assert resp_no_auth.status_code == 401

            resp_leads = await raw_client.get("/api/v1/leads")
            assert resp_leads.status_code == 401

            resp_campaigns = await raw_client.get("/api/v1/campaigns")
            assert resp_campaigns.status_code == 401

            resp_analytics = await raw_client.get("/api/v1/analytics/overview")
            assert resp_analytics.status_code == 401

            # 2. Invalid bearer token -> 401
            resp_bad_token = await raw_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer not_a_valid_jwt_token"},
            )
            assert resp_bad_token.status_code == 401
    finally:
        app.dependency_overrides = old_overrides


@pytest.mark.asyncio
async def test_auth_me_profile_and_memberships(client: AsyncClient):
    """Test retrieving authenticated user profile and memberships."""
    # Register a new user
    email = f"member_{uuid.uuid4().hex[:8]}@beta.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password789!",
            "full_name": "Beta Member",
            "organization_name": "Beta Labs",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    org_id = reg_resp.json()["organization"]["id"]

    # Temporarily remove overrides to test true token auth
    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as auth_client:
            me_resp = await auth_client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Organization-Id": org_id,
                },
            )
            assert me_resp.status_code == 200
            me_data = me_resp.json()
            assert me_data["user"]["email"] == email
            assert me_data["organization"]["id"] == org_id
            assert me_data["organization"]["role"] == "OWNER"
            assert len(me_data["organizations"]) >= 1
    finally:
        app.dependency_overrides = old_overrides


@pytest.mark.asyncio
async def test_multi_tenant_campaign_isolation():
    """Verify that Organization A and Organization B cannot view or modify each other's campaigns."""
    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as test_client:
            # Register User A in Org A
            email_a = f"tenant_a_{uuid.uuid4().hex[:8]}@alpha.com"
            reg_a = await test_client.post(
                "/api/v1/auth/register",
                json={
                    "email": email_a,
                    "password": "PasswordA123!",
                    "full_name": "User Alpha",
                    "organization_name": "Alpha Corp",
                },
            )
            assert reg_a.status_code == 201
            token_a = reg_a.json()["access_token"]
            org_a_id = reg_a.json()["organization"]["id"]

            # Register User B in Org B
            email_b = f"tenant_b_{uuid.uuid4().hex[:8]}@beta.com"
            reg_b = await test_client.post(
                "/api/v1/auth/register",
                json={
                    "email": email_b,
                    "password": "PasswordB123!",
                    "full_name": "User Beta",
                    "organization_name": "Beta Solutions",
                },
            )
            assert reg_b.status_code == 201
            token_b = reg_b.json()["access_token"]
            org_b_id = reg_b.json()["organization"]["id"]

            headers_a = {"Authorization": f"Bearer {token_a}", "X-Organization-Id": org_a_id}
            headers_b = {"Authorization": f"Bearer {token_b}", "X-Organization-Id": org_b_id}

            # User A creates a campaign in Org A
            create_camp_resp = await test_client.post(
                "/api/v1/campaigns",
                headers=headers_a,
                json={
                    "name": "Alpha Outbound AI Q4",
                    "description": "Targeting FinTech startups",
                    "icp_config": {
                        "target_industries": ["FinTech", "SaaS"],
                        "min_employees": 10,
                        "max_employees": 200,
                        "target_countries": ["US", "UK"],
                        "keywords": ["payments", "compliance"],
                        "required_technologies": ["Stripe", "Next.js"],
                        "custom_icp_prompt": "Must have verified compliance certifications.",
                    },
                },
            )
            assert create_camp_resp.status_code == 201
            camp_a_id = create_camp_resp.json()["id"]

            # User B lists campaigns -> should NOT see Alpha's campaign
            list_b = await test_client.get("/api/v1/campaigns", headers=headers_b)
            assert list_b.status_code == 200
            campaign_ids_b = [c["id"] for c in list_b.json()["items"]]
            assert camp_a_id not in campaign_ids_b

            # User B attempts to directly read User A's campaign -> 404
            get_b = await test_client.get(f"/api/v1/campaigns/{camp_a_id}", headers=headers_b)
            assert get_b.status_code == 404

            # User B attempts to patch User A's campaign -> 404
            patch_b = await test_client.patch(
                f"/api/v1/campaigns/{camp_a_id}",
                headers=headers_b,
                json={"name": "Hacked Alpha Campaign"},
            )
            assert patch_b.status_code == 404

            # User B attempts to delete User A's campaign -> 404
            del_b = await test_client.delete(f"/api/v1/campaigns/{camp_a_id}", headers=headers_b)
            assert del_b.status_code == 404

            # User A can view and update their campaign successfully
            get_a = await test_client.get(f"/api/v1/campaigns/{camp_a_id}", headers=headers_a)
            assert get_a.status_code == 200
            assert get_a.json()["name"] == "Alpha Outbound AI Q4"

            # User A can delete their campaign
            del_a = await test_client.delete(f"/api/v1/campaigns/{camp_a_id}", headers=headers_a)
            assert del_a.status_code == 204
    finally:
        app.dependency_overrides = old_overrides


@pytest.mark.asyncio
async def test_campaign_icp_prompt_conversion():
    """Verify campaign structured ICP config generates proper qualification prompt dictionary."""
    cfg = CampaignICPConfig(
        industries=["DevTools", "AI"],
        company_sizes=["11-50", "51-200"],
        geographies=["US", "Canada"],
        business_models=["B2B SaaS"],
        technologies=["Python", "FastAPI"],
        target_titles=["CTO", "Head of Engineering"],
        minimum_score=75,
    )
    profile_dict = cfg.to_icp_profile_dict()
    assert profile_dict["target_industries"] == ["DevTools", "AI"]
    assert profile_dict["target_company_size"] == ["11-50", "51-200"]
    assert profile_dict["target_geographies"] == ["US", "Canada"]
    assert profile_dict["min_icp_threshold"] == 75
    assert any("B2B SaaS" in s for s in profile_dict["required_signals"])
    assert any("Python" in s for s in profile_dict["required_signals"])


@pytest.mark.asyncio
async def test_analytics_endpoints_and_scoping(client: AsyncClient):
    """Test overview, usage, and leads analytics endpoints with tenant scoping."""
    # 1. Overview
    overview_resp = await client.get("/api/v1/analytics/overview")
    assert overview_resp.status_code == 200
    ov_data = overview_resp.json()
    assert "total_leads" in ov_data
    assert "qualification_rate" in ov_data
    assert "total_crawls" in ov_data
    assert "pages_crawled" in ov_data
    assert "estimated_ai_cost" in ov_data

    # 2. Daily Usage
    usage_resp = await client.get("/api/v1/analytics/usage")
    assert usage_resp.status_code == 200
    us_data = usage_resp.json()
    assert "items" in us_data

    # 3. Leads Distribution
    leads_resp = await client.get("/api/v1/analytics/leads")
    assert leads_resp.status_code == 200
    ld_data = leads_resp.json()
    assert "total_leads" in ld_data
    assert "by_campaign" in ld_data
    assert "by_industry" in ld_data
    assert "by_status" in ld_data


@pytest.mark.asyncio
async def test_job_concurrency_quota_limit():
    """Verify that AnalyticsService raises 429 when max active jobs per organization is exceeded."""
    from unittest.mock import AsyncMock, MagicMock
    from app.services.analytics_service import AnalyticsService

    db_mock = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db_mock.execute.return_value = mock_result

    analytics_service = AnalyticsService(db=db_mock)
    test_org_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await analytics_service.check_usage_limits(test_org_id)
    assert exc_info.value.status_code == 429
    assert "Active job limit reached" in exc_info.value.detail
