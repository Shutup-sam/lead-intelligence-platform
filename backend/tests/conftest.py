import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User
from app.models.organization import Organization
from app.core.auth import (
    get_current_user,
    get_current_organization,
    require_organization_member,
    require_organization_owner,
)

DEFAULT_TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEFAULT_TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

mock_user = User(
    id=DEFAULT_TEST_USER_ID,
    email="testuser@example.com",
    password_hash="$2b$12$xyz",
    full_name="Test User",
    is_active=True,
)
mock_org = Organization(
    id=DEFAULT_TEST_ORG_ID,
    name="Default Workspace",
    slug="default-workspace",
)


@pytest.fixture(autouse=True)
def setup_default_auth_overrides():
    """Provides default test auth overrides so existing Milestone 1-5 tests continue to pass seamlessly."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_organization] = lambda: (mock_org, "OWNER")
    app.dependency_overrides[require_organization_member] = lambda: (mock_org, "OWNER")
    app.dependency_overrides[require_organization_owner] = lambda: (mock_org, "OWNER")
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
