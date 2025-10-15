"""Fixtures for seed_licenses tests"""
import pytest
from rest_framework.test import APIClient
from utils.encrypt_aadhaar import encrypt_aadhaar


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture(autouse=True)
def mock_celery(monkeypatch):
    """Mock Celery to avoid Redis connection in tests"""
    monkeypatch.setattr(
        "apps.seed_licenses.views.write_to_contract",
        lambda *args, **kwargs: {
            "success": True,
            "data": {"transaction_hash": "0xmocked123"}
        }
    )


@pytest.fixture
def valid_license_payload():
    """Standard valid license application payload"""
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
        "isSeedSelfProduced": 'false',
        "productionCompany": "Company"
    }


@pytest.fixture
def valid_update_status_payload():
    """Standard valid status update payload"""
    return {
        "licenseId": 1,
        "status": "UNDER_REVIEW",
        "officerName": "Bob",
        "role": "AGRICULTURE_OFFICER",
        "renewalPeriodDays": 34,
        "remarks": "License is under review"
    }

