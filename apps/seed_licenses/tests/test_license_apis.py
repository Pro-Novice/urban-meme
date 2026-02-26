"""
Test cases for seed license endpoints.
Place this file as: tests/test_license_endpoints.py
"""
import pytest
from unittest.mock import MagicMock, patch
from django.urls import reverse, NoReverseMatch
from rest_framework import status
from apps.seed_licenses.tests.helper import (
    get_error_message,
    assert_success_response,
    assert_error_response,
    assert_has_keys,
    assert_transaction_accepted,
    assert_error_contains
)
from config import settings as settings
import time

# ============================================================================
# GET PUBLIC KEY TESTS
# ============================================================================

@pytest.mark.django_db
class TestGetPublicKey:
    """Tests for get-public-key endpoint"""
    
    def test_success(self, client, settings):
        """Test successful public key retrieval"""
        expected_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----"
        settings.GENERATED_PUBLIC_KEY = expected_key
        
        resp = client.get(reverse("get-public-key"))
        
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["success"] is True
        assert "public_key" in resp.json()["data"]
        assert "-----BEGIN PUBLIC KEY-----" in resp.json()["data"]["public_key"]
    
    @pytest.mark.parametrize("key_value", [None, ""])
    def test_public_key_not_available(self, client, settings, key_value):
        """Test when public key is not available"""
        settings.GENERATED_PUBLIC_KEY = key_value

        resp = client.get(reverse("get-public-key"))

        assert_error_contains(
            resp,
            "Public key not loaded from settings.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def test_unexpected_exception(self, client):
        """Test handling of unexpected exceptions"""
        with patch("apps.seed_licenses.views.security_view.settings") as mock_settings:
            mock_settings.GENERATED_PUBLIC_KEY = MagicMock(side_effect=RuntimeError("Settings corrupted"))
            
            resp = client.get(reverse("get-public-key"))
            
            assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert_error_contains(resp, "Error fetching public key", status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# LICENSE COUNT TESTS
# ============================================================================

@pytest.mark.django_db
class TestCheckTotalLicenseCount:
    """Tests for check-total-license-count endpoint"""
    
    @pytest.mark.parametrize("count", [0, 42, 100, 1000])
    def test_success_various_counts(self, client, monkeypatch, count):
        """Test with various license counts"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.tx_service.read",
            MagicMock(return_value=count)
        )
        
        resp = client.get(reverse("license-count"))
        
        assert_success_response(resp)
        assert resp.json()["data"]["total_licenses"] == count
    
    def test_value_error_invalid_method(self, client, monkeypatch):
        """Test when contract method doesn't exist"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.tx_service.read",
            MagicMock(side_effect=ValueError("Method 'licenseIdCounter' not found"))
        )
        
        resp = client.get(reverse("license-count"))
        
        assert_error_response(resp, status.HTTP_400_BAD_REQUEST, ["licenseIdCounter", "not found"])
    
    @pytest.mark.parametrize("exception,expected_status", [
        (ConnectionError("Blockchain node unreachable"), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (RuntimeError("Unexpected error"), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ])
    def test_exceptions(self, client, monkeypatch, exception, expected_status):
        """Test various exception scenarios"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.tx_service.read",
            MagicMock(side_effect=exception)
        )
        
        resp = client.get(reverse("license-count"))
        
        assert_error_response(resp, expected_status, ["error"])


# ============================================================================
# SUBMIT LICENSE APPLICATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestSubmitLicenseApplication:
    """Tests for submit-license-application endpoint"""

    def test_success(self, client, valid_license_payload, monkeypatch):
        """Test successful license submission"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.submit_application",
            MagicMock(return_value={"success": True, "transaction_hash": "0xabc123"})
        )

        resp = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json",
        )
        print(resp.json())
        print(resp.status_code)
        assert resp.status_code == status.HTTP_202_ACCEPTED
        data = resp.json()["data"]
        assert data["status"] == "accepted"
        assert "transaction_hash" in data
        assert data["licenseNumber"] == valid_license_payload["licenseNumber"]

    def test_duplicate_license_number(self, client, valid_license_payload, monkeypatch):
        """Test duplicate license number is rejected"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.submit_application",
            MagicMock(return_value={"success": True, "transaction_hash": "0xabc123"})
        )

        first = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json",
        )
        assert first.status_code == status.HTTP_202_ACCEPTED

        second = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json",
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST
    
    @pytest.mark.parametrize("field", [
        "licenseCategory", "licenseLevel", "registeringAuthority",
        "registeringOfficeName", "licenseNumber", "applicantName", "aadhaarNumber",
    ])
    def test_missing_required_fields(self, client, valid_license_payload, field):
        """Test missing required fields"""
        del valid_license_payload[field]
        
        resp = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json"
        )
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = get_error_message(resp)
        assert field.lower().replace("_", "") in error_msg.lower().replace("_", "")
    
    @pytest.mark.parametrize("field,invalid_value", [
        ("license_category", "INVALID_CATEGORY"),
        ("license_level", "INVALID_LEVEL"),
        ("applicant_name", ""),
    ])
    def test_invalid_field_values(self, client, valid_license_payload, field, invalid_value):
        """Test invalid field values"""
        valid_license_payload[field] = invalid_value
        
        resp = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json"
        )
        print(resp.json())
    
        assert_error_response(resp, status.HTTP_400_BAD_REQUEST, [field.lower()])
    
    def test_blockchain_transaction_failure(self, client, valid_license_payload, monkeypatch):
        """Test when blockchain transaction fails"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.submit_application",
            MagicMock(return_value={
                "success": False,
                "error": "Transaction reverted by contract"
            })
        )
        
        resp = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json"
        )
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_service_exception(self, client, valid_license_payload, monkeypatch):
        """Test service layer exception"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.submit_application",
            MagicMock(side_effect=RuntimeError("Service error"))
        )
        
        resp = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json"
        )
        
        assert_error_response(resp, status.HTTP_500_INTERNAL_SERVER_ERROR, ["error"])
    
    def test_invalid_json_format(self, client):
        """Test with invalid JSON format"""
        resp = client.post(
            reverse("submit-license-application"),
            data="invalid json",
            content_type="application/json"
        )
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# GET LICENSE BASIC INFO TESTS
# ============================================================================

@pytest.mark.django_db
class TestGetLicenseBasicInfo:
    """Tests for get-license-basic-info endpoint"""
    
    EXPECTED_KEYS = {
        "licenseNumber", "applicantName", "category", "level", "status",
        "firmName", "firmType", "firmAddress", "salePointAddress", "saleStorageAddress",
        "productionCompany", "cropName", "cropVariety", "registeringOfficeName",
        "registeringAuthority", "applicationDate", "isActive"
    }
    
    def test_success(self, client, valid_license_payload, mock_license_data, monkeypatch):
        """Test successful license info retrieval"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_basic_info",
            MagicMock(return_value=mock_license_data)
        )
        resp = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json",
        )
        from apps.seed_licenses.models import LicenseSubmission
        LicenseSubmission.objects.filter(license_number=valid_license_payload["licenseNumber"]).update(
            license_id=1
        )
        resp = client.get(reverse("license-basic-info", args=[1]))
        
        assert_success_response(resp)
        data = resp.json()["data"]
        
        assert_has_keys(data, self.EXPECTED_KEYS)
        assert "licenseId" not in data
        assert data["licenseNumber"] == valid_license_payload["licenseNumber"]
    
    @pytest.mark.parametrize("license_id", [1, 10, 100, 1000, 9999])
    def test_valid_positive_license_ids(self, client, monkeypatch, license_id):
        """Test with various valid positive IDs"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_basic_info",
            MagicMock(return_value={"licenseId": license_id})
        )
        
        resp = client.get(reverse("license-basic-info", args=[license_id]))
        assert_success_response(resp)
    
    def test_non_existent_license(self, client, monkeypatch):
        """Test requesting non-existent license"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_basic_info",
            MagicMock(side_effect=Exception("License not found"))
        )
        
        resp = client.get(reverse("license-basic-info", args=[999]))
        print(resp.json())
        assert_error_response(resp, status.HTTP_500_INTERNAL_SERVER_ERROR, ["license", "not found"])
    
    @pytest.mark.parametrize("invalid_id", ["abc", "12.34", "-1"])
    def test_invalid_license_ids(self, invalid_id):
        """Test with invalid license IDs"""
        with pytest.raises(NoReverseMatch):
            reverse("license-basic-info", args=[invalid_id])
    
    def test_zero_license_id(self, client, monkeypatch):
        """Test with zero license ID"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_basic_info",
            MagicMock(side_effect=ValueError("Invalid license ID"))
        )
        
        resp = client.get(reverse("license-basic-info", args=[0]))
        
        assert resp.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.parametrize("exception", [
        ConnectionError("Blockchain unreachable"),
        RuntimeError("Service error"),
    ])
    def test_exceptions(self, client, monkeypatch, exception):
        """Test exception handling"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_basic_info",
            MagicMock(side_effect=exception)
        )
        
        resp = client.get(reverse("license-basic-info", args=[15]))
        print(resp.json())
        
        assert_error_response(resp, status.HTTP_500_INTERNAL_SERVER_ERROR, ["error"])


# ============================================================================
# GET LICENSE QR DATA TESTS
# ============================================================================

@pytest.mark.django_db
class TestGetLicenseQRData:
    """Tests for get-license-qr-data endpoint"""
    
    def test_success(self, client, mock_qr_data, monkeypatch):
        """Test successful QR data retrieval"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_qr_data",
            MagicMock(return_value=mock_qr_data)
        )
        
        resp = client.get(reverse("license-qr-data", args=[1]))
        
        assert_success_response(resp)
        data = resp.json()["data"]
        assert "verificationHash" in data
        assert "licenseNumber" in data
        assert data["licenseNumber"] == "LIC001"
    
    @pytest.mark.parametrize("license_id", [1, 50, 100, 500])
    def test_various_valid_license_ids(self, client, monkeypatch, license_id):
        """Test with various valid license IDs"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_qr_data",
            MagicMock(return_value={"verificationHash": "hash", "licenseNumber": "LIC001"})
        )
        
        resp = client.get(reverse("license-qr-data", args=[license_id]))
        assert_success_response(resp)
    
    @pytest.mark.parametrize("invalid_id", ["abc", "#$", "-987"])
    def test_invalid_license_ids(self, invalid_id):
        """Test with invalid license IDs"""
        with pytest.raises(NoReverseMatch):
            reverse("license-qr-data", args=[invalid_id])
    
    def test_zero_license_id(self, client, monkeypatch):
        """Test with zero license ID"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_qr_data",
            MagicMock(side_effect=ValueError("Invalid license ID"))
        )
        
        resp = client.get(reverse("license-qr-data", args=[0]))
        
        assert resp.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.parametrize("exception,keyword", [
        (Exception("License must be active to generate QR data"), "active"),
        (ConnectionError("Blockchain connection failed"), "error"),
        (RuntimeError("Unexpected error"), "error"),
    ])
    def test_exceptions(self, client, monkeypatch, exception, keyword):
        """Test exception scenarios"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_qr_data",
            MagicMock(side_effect=exception)
        )
        
        resp = client.get(reverse("license-qr-data", args=[19]))
        
        assert_error_response(resp, status.HTTP_500_INTERNAL_SERVER_ERROR, [keyword])


# ============================================================================
# GET LICENSE ACTION HISTORY TESTS
# ============================================================================

@pytest.mark.django_db
class TestGetLicenseActionHistory:
    """Tests for get-license-action-history endpoint"""
    
    def test_success_with_actions(self, client, mock_action_history, monkeypatch):
        """Test successful history retrieval with actions"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_action_history",
            MagicMock(return_value=mock_action_history)
        )
        from apps.seed_licenses.models import LicenseSubmission
        LicenseSubmission.objects.create(license_number="RJSDST-TEST-001", license_id=1)
        
        resp = client.get(reverse("license-action-history", args=[1]))
        
        assert_success_response(resp)
        data = resp.json()["data"]
        assert isinstance(data, dict)
        assert data["licenseNumber"] == "RJSDST-TEST-001"
        assert isinstance(data["history"], list)
        assert len(data["history"]) == 2
        assert data["history"][0]["actionType"] == "SUBMITTED"
        assert data["history"][1]["actionType"] == "APPROVED"
    
    def test_multiple_actions_ordering(self, client, monkeypatch):
        """Test that actions are returned in correct order"""
        mock_history = [
            {"timestamp": "2025-01-01", "actionType": "SUBMITTED"},
            {"timestamp": "2025-01-02", "actionType": "UNDER_REVIEW"},
            {"timestamp": "2025-01-03", "actionType": "APPROVED"}
        ]
        
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_action_history",
            MagicMock(return_value=mock_history)
        )
        from apps.seed_licenses.models import LicenseSubmission
        LicenseSubmission.objects.create(license_number="RJSDST-TEST-002", license_id=1)
        
        resp = client.get(reverse("license-action-history", args=[1]))
        
        assert_success_response(resp)
        data = resp.json()["data"]
        assert len(data["history"]) == 3
    
    @pytest.mark.parametrize("invalid_id", ["abc", -5])
    def test_invalid_license_ids(self, invalid_id):
        """Test with invalid license IDs"""
        with pytest.raises(NoReverseMatch):
            reverse("license-action-history", args=[invalid_id])
    
    @pytest.mark.parametrize("exception", [
        Exception("License does not exist"),
        ConnectionError("Blockchain unreachable"),
        RuntimeError("Service error"),
    ])
    def test_exceptions(self, client, monkeypatch, exception):
        """Test exception handling"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_action_history",
            MagicMock(side_effect=exception)
        )
        
        resp = client.get(reverse("license-action-history", args=[1]))
        
        assert_error_response(resp, status.HTTP_500_INTERNAL_SERVER_ERROR, ["error"])


# ============================================================================
# UPDATE LICENSE STATUS TESTS
# ============================================================================

@pytest.mark.django_db
class TestUpdateLicenseStatus:
    """Tests for update-license-status endpoint"""
    
    def test_idempotent_same_status(self, client, valid_license_payload, valid_status_payload, monkeypatch):
        """Test re-updating to the same status (idempotent)"""
        # Mock submit license endpoint
        monkeypatch.setattr(
        "apps.seed_licenses.views.license_view.license_service.submit_application",
        MagicMock(return_value={"success": True, "license_id": 1})
    )

        # Mock update status
        monkeypatch.setattr(
        "apps.seed_licenses.views.license_view.license_service.update_status",
        MagicMock(return_value={
            "success": True,
            "data": {
                "status": "no_change",
                "message": "License already in status UNDER_REVIEW"
            }
        })
    )

        # First call: submit license
        client.post(reverse("submit-license-application"), data=valid_license_payload, format="json")
        time.sleep(10)

        # Two repeated calls
        client.post(reverse("update-license-status"), data=valid_status_payload, format="json")
        
        resp = client.post(reverse("update-license-status"), data=valid_status_payload, format="json")
        status_code=resp.status_code
        assert_transaction_accepted(resp)
       


    def test_valid_transition(self, client, valid_status_payload, monkeypatch):
        """Test valid status transition"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.update_status",
            MagicMock(return_value={
                "success": True,
                "transaction_hash": "0xabc123",
                "changed": True
            })
        )

        resp = client.post(
            reverse("update-license-status"),
            data=valid_status_payload,
            format="json"
        )
        
        assert_transaction_accepted(resp)

    def test_forbidden_transition(self, client, valid_status_payload, monkeypatch):
        """Test forbidden status transition"""
        valid_status_payload["new_status"] = "SUBMITTED"

        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.update_status",
            MagicMock(side_effect=ValueError("Invalid transition from APPROVED to SUBMITTED"))
        )

        resp = client.post(
            reverse("update-license-status"),
            data=valid_status_payload,
            format="json"
        )

        assert resp.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]
        error_msg = get_error_message(resp)
        assert "transition" in error_msg.lower() or "invalid" in error_msg.lower()

    def test_missing_required_fields(self, client):
        """Test with missing required fields"""
        payload = {"license_id": 1}

        resp = client.post(
            reverse("update-license-status"),
            data=payload,
            format="json"
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_blockchain_reverts(self, client, valid_status_payload, monkeypatch):
        """Test blockchain transaction revert"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.update_status",
            MagicMock(return_value={
                "success": False,
                "error": "Transaction reverted"
            })
        )

        resp = client.post(
            reverse("update-license-status"),
            data=valid_status_payload,
            format="json"
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "current_status,next_status,should_pass",
        [
            ("SUBMITTED", "UNDER_REVIEW", True),
            ("UNDER_REVIEW", "DOCUMENT_VERIFICATION", True),
            ("DOCUMENT_VERIFICATION", "INSPECTION_SCHEDULED", True),
            ("INSPECTION_SCHEDULED", "INSPECTION_COMPLETED", True),
            ("INSPECTION_COMPLETED", "APPROVED", True),
            ("SUBMITTED", "APPROVED", False),
            ("UNDER_REVIEW", "APPROVED", False),
            ("DOCUMENT_VERIFICATION", "APPROVED", False),
            ("INSPECTION_COMPLETED", "SUBMITTED", False),
        ]
    )
    def test_enforce_status_sequence(self, client, valid_status_payload, current_status, 
                                     next_status, should_pass, monkeypatch):
        """Ensure license follows correct status flow"""
        valid_status_payload["new_status"] = next_status

        if should_pass:
            mock_return = {"success": True, "changed": True, "transaction_hash": "0xabc123"}
            monkeypatch.setattr(
                "apps.seed_licenses.views.license_view.license_service.update_status",
                MagicMock(return_value=mock_return)
            )
        else:
            monkeypatch.setattr(
                "apps.seed_licenses.views.license_view.license_service.update_status",
                MagicMock(side_effect=ValueError(f"Invalid transition from {current_status} to {next_status}"))
            )

        resp = client.post(
            reverse("update-license-status"),
            data=valid_status_payload,
            format="json"
        )

        if should_pass:
            assert_transaction_accepted(resp)
        else:
            assert_error_response(resp, 
                status.HTTP_400_BAD_REQUEST,
                ["invalid", "transition"])


# ============================================================================
# VERIFY DOCUMENT TESTS
# ============================================================================

@pytest.mark.django_db
class TestVerifyDocument:
    """Tests for verify-document endpoint"""
    
    def test_success(self, client, valid_license_payload,valid_status_payload,valid_verify_payload, monkeypatch):
        """Test successful document verification"""
        
        # Mock submit license endpoint
        monkeypatch.setattr(
        "apps.seed_licenses.views.license_view.license_service.submit_application",
        MagicMock(return_value={"success": True, "license_id": 1})
    )
         # Mock update_status to always succeed
        monkeypatch.setattr(
        "apps.seed_licenses.views.license_view.license_service.update_status",
        MagicMock(return_value={
            "success": True,
            "changed": True,
            "transaction_hash": "0xabc123"
        })
    )
        #Mock qr data
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.get_qr_data",
            MagicMock(return_value={"qr": "dummy-qr-data"})
        )
        # Mock verify_license_document
        # ⭐ THE IMPORTANT FIX ⭐
        monkeypatch.setattr(
        "apps.seed_licenses.views.license_view.license_service.verify_document",
        MagicMock(return_value={
            "success": True,
            "verified": True,
            "license_number": "RJSDST1"
        }))
        # 1. Submit license
        client.post(reverse("submit-license-application"), data=valid_license_payload, format="json")

        # 2. Move through all required transitions up to APPROVED
        status_flow = [
        "UNDER_REVIEW",
        "DOCUMENT_VERIFICATION",
        "INSPECTION_SCHEDULED",
        "INSPECTION_COMPLETED",
        "APPROVED",
    ]

        for s in status_flow:
            print("Updating status to:", s)
            valid_status_payload["new_status"] = s
            resp1=client.post(reverse("update-license-status"), data=valid_status_payload, format="json")
            print("Status updated to:", s," Response:", resp1.json())
        client.get(reverse("license-qr-data", args=[1]))

        
        resp = client.post(
            reverse("verify-license-document"),
            data=valid_verify_payload,
            format="json"
        )
        
        assert_transaction_accepted(resp)
    
    @pytest.mark.parametrize("missing_field,keyword", [
        ("licenseNumber", "license"),
        ("expectedHash", "hash"),
    ])
    def test_missing_fields(self, client, valid_verify_payload, missing_field, keyword):
        """Test missing required fields"""
        del valid_verify_payload[missing_field]
        
        resp = client.post(
            reverse("verify-license-document"),
            data=valid_verify_payload,
            format="json"
        )
        
        assert_error_response(resp, status.HTTP_400_BAD_REQUEST, [keyword])
    
    def test_invalid_hash_format(self, client, valid_verify_payload):
        """Test with invalid hash format"""
        valid_verify_payload["expectedHash"] = "invalid"
        
        resp = client.post(
            reverse("verify-license-document"),
            data=valid_verify_payload,
            format="json"
        )
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# UPDATE LICENSE DETAILS TESTS
# ============================================================================

@pytest.mark.django_db
class TestUpdateLicenseDetails:
    """Tests for update-license-details endpoint"""
    
    def test_success(self, client, valid_update_payload, monkeypatch):
        """Test successful license update"""
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.update_details",
            MagicMock(return_value={
                "success": True,
                "transaction_hash": "0xdef456",
                "changed": True
            })
        )
        
        resp = client.post(
            reverse("update-license-details"),
            data=valid_update_payload,
            format="json"
        )
        
        assert_transaction_accepted(resp)
    
    def test_only_optional_fields(self, client, monkeypatch):
        """Test update with only optional fields"""
        payload = {
            "licenseId": 2,
            "firmName": "Updated Address 123",
            "firmType": "Updated Address 123",
            "firmAddress": "Updated Address 123",
            "role": "AGRICULTURE_OFFICER"   
        }
        
        monkeypatch.setattr(
            "apps.seed_licenses.views.license_view.license_service.update_details",
            MagicMock(return_value={
                "success": True,
                "transaction_hash": "0xabc",
                "changed": True
            })
        )
        
        resp = client.post(
            reverse("update-license-details"),
            data=payload,
            format="json"
        )
        
        assert_transaction_accepted(resp)
    
    def test_invalid_license_id_type(self, client):
        """Test with invalid license_id type"""
        payload = {
            "licenseId": "invalid",
            "firmAddress": "New Address"
        }
        
        resp = client.post(
            reverse("update-license-details"),
            data=payload,
            format="json"
        )
        
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
    