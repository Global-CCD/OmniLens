"""
OmniLens v3.0 - API Endpoint Tests
Tests for FastAPI endpoints using TestClient and async database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
from config import settings

# Test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_db():
    """Create test database tables before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["app"] == "OmniLens"
        assert "version" in data
        assert "database" in data
        assert "providers" in data


class TestPhotosEndpoint:
    def test_get_photos_empty(self):
        response = client.get("/photos")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["count"] == 0
        assert data["data"] == []

    def test_get_photos_pagination(self):
        response = client.get("/photos?skip=0&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 10


class TestScanEndpoint:
    def test_scan_invalid_provider(self):
        response = client.post("/scan", json={"provider": "invalid"})
        assert response.status_code == 422  # Validation error

    def test_scan_all_providers(self):
        response = client.post("/scan", json={"provider": "all"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running_in_background"

    def test_scan_google_provider(self):
        response = client.post("/scan", json={"provider": "google"})
        # May return 400 if not configured, or 200 if configured
        assert response.status_code in [200, 400]


class TestWebhookEndpoints:
    def test_google_webhook_no_token(self):
        response = client.post("/webhook/google")
        # Should fail without token if configured
        assert response.status_code in [200, 401]

    def test_s3_webhook_no_signature(self):
        response = client.post("/webhook/s3")
        # Should fail without signature if configured
        assert response.status_code in [200, 401]


class TestSyncHistory:
    def test_sync_history_empty(self):
        response = client.get("/sync-history")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
