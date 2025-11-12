"""
Pytest fixtures for seed license tests.
Place this file as: tests/conftest.py
"""
import pytest
import subprocess
import time
from rest_framework.test import APIClient
from utils.encrypt_aadhaar import encrypt_aadhaar
from unittest.mock import MagicMock

@pytest.fixture
def client():
    """API client for making requests"""
    return APIClient()


@pytest.fixture(scope="session", autouse=False)
def reset_blockchain():
    """Reset blockchain before tests"""
    subprocess.run(["pkill", "-f", "ganache-cli"], stderr=subprocess.DEVNULL)
    subprocess.Popen(["npx", "ganache-cli", "--deterministic", "--port", "8545"])
    time.sleep(5)
    yield
    subprocess.run(["pkill", "-f", "ganache-cli"], stderr=subprocess.DEVNULL)


@pytest.fixture
def valid_license_payload():
    """Valid license application payload"""
    return {
        "licenseCategory": "SEED",
        "licenseLevel": "DISTRICT",
        "registeringAuthority": "Govt",
        "registeringOfficeName": "Dept",
        "applicantName": "Alice",
        "aadhaarNumber": encrypt_aadhaar("234567890123"),
        "applicantPermanentAddress": "Addr1",
        "firmName": "Firm",
        "firmType": "Private",
        "firmAddress": "Firm Addr",
        "salePointAddress": "Sale Addr",
        "saleStorageAddress": "Storage Addr",
        "cropName": "Crop",
        "cropVariety": "Variety",
        "isSeedSelfProduced": False,
        "productionCompany": "Company"
    }


@pytest.fixture
def valid_status_payload():
    """Valid status update payload"""
    return {
        "licenseId": 2,
        "status": "UNDER_REVIEW",
        "officerName": "Officer Smith",
        "role": "AGRICULTURE_OFFICER",
        "remarks": "Application approved after review"
    }


@pytest.fixture
def valid_verify_payload():
    """Valid document verification payload"""
    return {
        "licenseNumber": "RJSDST1",
        "expectedHash": "abc123def456789"
    }


@pytest.fixture
def valid_update_payload():
    """Valid license update payload"""
    return {
        "licenseId": 1,
        "firmName": "Updated Address 123",
        "firmType": "Updated Address 123",
        "firmAddress": "Updated Address 123",
        "salePointAddress": "New Sale Point",
        "cropVariety": "Officer Smith",
        "role": "AGRICULTURE_OFFICER"
    }


@pytest.fixture
def mock_license_data():
    """Complete mock license data for testing"""
    return {
        "licenseId": 1,
        "licenseNumber": "LIC001",
        "applicantName": "John Doe",
        "category": "SEED_DEALER",
        "level": "STATE",
        "status": "APPROVED",
        "firmName": "Test Firm",
        "firmType": "Private",
        "firmAddress": "123 Test St",
        "salePointAddress": "456 Sale St",
        "saleStorageAddress": "789 Storage St",
        "productionCompany": "Test Company",
        "cropName": "Wheat",
        "cropVariety": "HD-2967",
        "registeringOfficeName": "Test Office",
        "registeringAuthority": "Test Authority",
        "applicationDate": "2025-01-01",
        "isActive": True
    }


@pytest.fixture
def mock_action_history():
    """Mock action history data"""
    return [
        {
            "timestamp": "2025-01-01 10:00:00",
            "actionType": "SUBMITTED",
            "actorName": "John Doe",
            "actorRole": "CITIZEN",
            "remarks": "Application submitted",
            "dataHash": "hash123"
        },
        {
            "timestamp": "2025-01-02 11:00:00",
            "actionType": "APPROVED",
            "actorName": "Officer Smith",
            "actorRole": "AGRICULTURE_OFFICER",
            "remarks": "Application approved",
            "dataHash": "hash456"
        }
    ]


@pytest.fixture
def mock_qr_data():
    """Mock QR data"""
    return {
        "verificationHash": "abc123def456",
        "licenseNumber": "LIC001",
        "status": "APPROVED"
    }
    
@pytest.fixture(autouse=True)
def mock_celery_and_redis(monkeypatch):
    """Mock Celery + Redis backend so no real broker or result backend is needed."""

    # Mock Celery async calls
    monkeypatch.setattr("celery.app.base.Celery.send_task", lambda *a, **kw: None)
    monkeypatch.setattr("celery.app.task.Task.delay", lambda *a, **kw: None)
    monkeypatch.setattr("celery.app.task.Task.apply_async", lambda *a, **kw: None)

    # Mock Redis client
    class DummyRedis:
        def get(self, key): return None
        def set(self, key, value): return True
        def delete(self, key): return True

    monkeypatch.setattr("redis.Redis", lambda *a, **kw: DummyRedis())

