import pytest
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
import apps.seed_licenses.services.blockchain as blockchain_service
import apps.seed_licenses.views as views_module
from  apps.seed_licenses.Tests.helper import assert_error_contains, mock_contract_read, mock_contract_write
from  apps.seed_licenses.Tests.fixtures import client, valid_license_payload, valid_update_status_payload,mock_celery



# ============================================================================
# PUBLIC KEY TESTS
# ============================================================================

@pytest.mark.django_db
def test_get_public_key(client):
    url = reverse("get-public-key")
    resp = client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert "-----BEGIN PUBLIC KEY-----" in resp.json()["data"]


# ============================================================================
# CONTRACT OWNER TESTS
# ============================================================================

@pytest.mark.django_db
class TestCheckOwner:
    """Tests for check-owner endpoint"""
    
    def test_success(self, client, monkeypatch):
        expected_owner = "0xFE3B557E8Fb62b89F4916B721be55cEb828dBd73"
        monkeypatch.setattr(
            blockchain_service, 
            "read_from_contract", 
            lambda method_name, params: expected_owner
        )
        
        resp = client.get(reverse("check-owner"))
        assert resp.status_code == 200
        assert resp.json()["data"] == expected_owner
    
    def test_value_error(self, client, monkeypatch):
        mock_contract_read(monkeypatch, side_effect=ValueError("Method 'owner' not found"))
        resp = client.get(reverse("check-owner"))
        assert_error_contains(resp, "Method 'owner' not found")
    
    def test_unexpected_error(self, client, monkeypatch):
        mock_contract_read(monkeypatch, side_effect=Exception("Blockchain node unreachable"))
        resp = client.get(reverse("check-owner"))
        assert_error_contains(resp, "Blockchain read failed", 500)


# ============================================================================
# LICENSE COUNT TESTS
# ============================================================================

@pytest.mark.django_db
class TestLicenseCount:
    """Tests for license-count endpoint"""
    
    def test_success(self, client):
        resp = client.get(reverse("license-count"))
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json()["data"], int)
        assert resp.json()["data"] >= 0
    
    def test_invalid_method(self, client, monkeypatch):
        mock_contract_read(monkeypatch, side_effect=ValueError("Method 'licenseIdCounter' not found"))
        resp = client.get(reverse("license-count"))
        assert_error_contains(resp, "licenseIdCounter")
    
    @pytest.mark.parametrize("error_msg", [
        "Connection error: Blockchain node unreachable",
        "Timeout while reading from blockchain"
    ])
    def test_blockchain_errors(self, client, monkeypatch, error_msg):
        mock_contract_read(monkeypatch, side_effect=Exception(error_msg))
        resp = client.get(reverse("license-count"))
        assert_error_contains(resp, "Blockchain write failed", 500)


# ============================================================================
# SUBMIT LICENSE APPLICATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestSubmitLicenseApplication:
    """Tests for submit-license-application endpoint"""
    
    def test_success(self, client, valid_license_payload):
        resp = client.post(
            reverse("submit-license-application"), 
            data=valid_license_payload, 
            format="json"
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        assert "transaction_hash" in resp.json()["data"]
    
    def test_invalid_input(self, client):
        resp = client.post(
            reverse("submit-license-application"),
            data={"applicantName": "Alice"},
            format="json"
        )
        assert_error_contains(resp, "license_category")
    
    def test_blockchain_failure(self, client, monkeypatch, valid_license_payload):
        mock_contract_write(monkeypatch, return_value={
            "success": False, 
            "error": "Contract rejected transaction"
        })
        
        resp = client.post(
            reverse("submit-license-application"),
            data=valid_license_payload,
            format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_exception(self, client, valid_license_payload):
        with patch("apps.seed_licenses.views.write_to_contract", side_effect=Exception("Node connection failed")):
            resp = client.post(
                reverse("submit-license-application"),
                data=valid_license_payload,
                format="json"
            )
            assert_error_contains(resp, "Create license failed", 500)


# ============================================================================
# GET LICENSE BASIC INFO TESTS
# ============================================================================

@pytest.mark.django_db
class TestGetLicenseBasicInfo:
    """Tests for license-basic-info endpoint"""
    
    EXPECTED_KEYS = {
        "licenseId", "licenseNumber", "applicantName", "category", "level", "status",
        "firmName", "firmType", "firmAddress", "salePointAddress", "saleStorageAddress",
        "productionCompany", "cropName", "cropVariety", "registeringOfficeName",
        "registeringAuthority", "applicationDate", "expiryDate", "isActive"
    }
    
    def test_success(self, client):
        resp = client.get(reverse("license-basic-info", args=[1]))
        assert resp.status_code == status.HTTP_200_OK
        
        resp_json = resp.json()
        assert resp_json["success"] is True
        
        missing_keys = self.EXPECTED_KEYS - resp_json["data"].keys()
        assert not missing_keys, f"Missing keys: {missing_keys}"
    
    def test_non_integer_id(self, client):
        resp = client.get(reverse("license-basic-info", args=["abc"]))
        assert_error_contains(resp, "License ID must be a valid integer")
    
    def test_negative_id(self, client):
        resp = client.get(reverse("license-basic-info", args=[-5]))
        assert_error_contains(resp, "License ID must be positive integer")
    
    def test_blockchain_failure(self, client, monkeypatch):
        mock_contract_read(monkeypatch, side_effect=Exception("Blockchain unreachable"))
        resp = client.get(reverse("license-basic-info", args=[1]))
        assert_error_contains(resp, "License information unavailable", 500)


# ============================================================================
# UPDATE LICENSE STATUS TESTS
# ============================================================================

@pytest.mark.django_db
class TestUpdateLicenseStatus:
    """Tests for update-license-status endpoint"""
    
    def test_success(self, client, valid_update_status_payload):
        with patch("apps.seed_licenses.views.read_from_contract", return_value={"status": "SUBMITTED"}), \
             patch("apps.seed_licenses.views.write_to_contract", return_value={
                 "success": True,
                 "data": {
                     "transaction_hash": "0xabc123",
                     "status": "accepted",
                     "message": "Transaction submitted successfully. Processing will continue in the background."
                 }
             }):
            
            resp = client.post(
                reverse("update-license-status"),
                data=valid_update_status_payload,
                format="json"
            )
            
            assert resp.status_code == 202
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["status"] == "accepted"
            assert "Transaction submitted" in data["data"]["message"]
    
    def test_invalid_transition(self, client, monkeypatch):
        monkeypatch.setattr(
            views_module, "write_to_contract",
            lambda *args, **kwargs: {"status": "UNDER_REVIEW"}
        )
        
        resp = client.post(
            reverse("update-license-status"),
            data={
                "licenseId": 1,
                "status": "APPROVED",
                "officerName": "Shrawan",
                "role": "AGRICULTURE_OFFICER",
                "remarks": "Trying invalid transition",
                "renewalPeriodDays": 34
            },
            format="json"
        )
        assert_error_contains(resp, "Invalid status transition")
    
    def test_missing_renewal_period(self, client):
        resp = client.post(
            reverse("update-license-status"),
            data={
                "licenseId": 1,
                "status": "APPROVED",
                "officerName": "Shrawan",
                "role": "AGRICULTURE_OFFICER",
                "remarks": "Missing renewal period"
            },
            format="json"
        )
        assert_error_contains(resp, "renewal_period_days")
    
    def test_invalid_status_value(self, client):
        resp = client.post(
            reverse("update-license-status"),
            data={
                "licenseId": 1,
                "status": "INVALID_STATUS",
                "officerName": "Bob",
                "role": "AGRICULTURE_OFFICER",
                "remarks": "Invalid status test"
            },
            format="json"
        )
        assert_error_contains(resp, "Invalid license status")
    
    def test_blockchain_write_failed(self, client, monkeypatch):
        mock_contract_write(monkeypatch, return_value={
            "success": False,
            "error": "Reverted by EVM"
        })
        
        resp = client.post(
            reverse("update-license-status"),
            data={
                "licenseId": 1,
                "status": "UNDER_REVIEW",
                "officerName": "Bob",
                "role": "AGRICULTURE_OFFICER",
                "remarks": "Blockchain rejection"
            },
            format="json"
        )
        assert resp.status_code == 400
        assert resp.json()["success"] is False
    
    def test_unexpected_error(self, client):
        with patch("apps.seed_licenses.views.read_from_contract", return_value={"status": "APPLIED"}), \
             patch("apps.seed_licenses.views.write_to_contract", side_effect=ZeroDivisionError("division by zero")):
            
            resp = client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": 2,
                    "status": "APPROVED",
                    "officerName": "Shrawan",
                    "role": "AGRICULTURE_OFFICER",
                    "renewalPeriodDays": 34,
                    "remarks": "License is UNDER_REVIEW"
                },
                format="json"
            )
            assert_error_contains(resp, "Update license status failed", 500)
    
    @pytest.mark.parametrize("field", ["officer_name", "remarks"])
    def test_empty_fields(self, client, field):
        payload = {
            "licenseId": 1,
            "status": "UNDER_REVIEW",
            "officerName": "Bob",
            "role": "AGRICULTURE_OFFICER",
            "remarks": "Reasonable"
        }
        payload[field] = ""
        
        resp = client.post(reverse("update-license-status"), data=payload, format="json")
        assert_error_contains(resp, field)


# ============================================================================
# VERIFY LICENSE DOCUMENT TESTS
# ============================================================================

@pytest.mark.django_db
class TestVerifyLicenseDocument:
    """Tests for verify-license-document endpoint"""
    
    def test_success(self, client, monkeypatch):
        mock_contract_write(monkeypatch, return_value={
            "success": True,
            "transaction_hash": "0xabc123"
        })
        
        resp = client.post(
            reverse("verify-license-document"),
            data={"licenseNumber": "RJSDST2", "expectedHash": "abcdef"},
            format="json"
        )
        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["status"] == "accepted"
        assert "transaction_hash" in data
    
    @pytest.mark.parametrize("payload,error_key", [
        ({"licenseNumber": "", "expectedHash": "abcdef"}, "license_number"),
        ({"licenseNumber": "LIC123", "expectedHash": ""}, "expected_hash")
    ])
    def test_missing_fields(self, client, payload, error_key):
        resp = client.post(reverse("verify-license-document"), data=payload, format="json")
        assert resp.status_code == 400
        assert error_key in resp.json()["error"]
    
    def test_blockchain_fail(self, client, monkeypatch):
        mock_contract_write(monkeypatch, return_value={
            "success": False,
            "error": "Transaction failed",
            "details": "Execution reverted (License application is under review)"
        })
        
        resp = client.post(
            reverse("verify-license-document"),
            data={"licenseNumber": "LIC123", "expectedHash": "abcdef"},
            format="json"
        )
        assert resp.status_code == 400
        assert resp.json()["data"]["success"] is False
        assert "Transaction failed" in resp.json()["data"]["error"]
    
    def test_unexpected_exception(self, client, monkeypatch):
        mock_contract_write(monkeypatch, side_effect=RuntimeError("Unexpected failure"))
        
        resp = client.post(
            reverse("verify-license-document"),
            data={"licenseNumber": "LIC123", "expectedHash": "abcdef"},
            format="json"
        )
        assert_error_contains(resp, "Verify document failed", 500)


# ============================================================================
# LICENSE ACTION HISTORY TESTS
# ============================================================================

@pytest.mark.django_db
class TestGetLicenseActionHistory:
    """Tests for license-action-history endpoint"""
    
    def test_success(self, client):
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", return_value=[
            {
                "timestamp": "14 October 2025",
                "actionType": "SUBMITTED",
                "actorName": "Ravi Kumar",
                "actorRole": "CITIZEN",
                "remarks": "License Application Successfully Submitted",
                "dataHash": "14fc6f02faff112e3cb4b6f2df0ce53e9a628639cea9c03bc751f2df285bc1e8"
            }
        ]):
            resp = client.get(reverse("license-action-history", args=[1]))
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert isinstance(data, list)
            assert data[0]["actionType"] == "SUBMITTED"
    
    def test_invalid_license_id_non_integer(self, client):
        resp = client.get(reverse("license-action-history", args=["abc"]))
        assert_error_contains(resp, "License ID must be a valid integer")
    
    def test_invalid_license_id_negative(self, client):
        resp = client.get(reverse("license-action-history", args=[-5]))
        assert_error_contains(resp, "License ID must be positive integer")
    
    def test_value_error_from_contract(self, client):
        with patch("apps.seed_licenses.views.read_from_contract", side_effect=ValueError("License ID does not exist")):
            resp = client.get(reverse("license-action-history", args=[999]))
            assert_error_contains(resp, "License ID does not exist")
    
    def test_unexpected_exception(self, client):
        with patch("apps.seed_licenses.views.read_from_contract", side_effect=Exception("Unexpected failure")):
            resp = client.get(reverse("license-action-history", args=[1]))
            assert_error_contains(resp, "Blockchain write failed", 500)


# ============================================================================
# UPDATE LICENSE DETAILS TESTS
# ============================================================================

@pytest.mark.django_db
class TestUpdateLicenseDetails:
    """Tests for update-license-details endpoint"""
    
    def test_success(self, client):
        payload = {
            "licenseId": 1,
            "firmName": "New Firm Name",
            "firmType": "New Firm Type",
            "firmAddress": "New Firm Address",
            "salePointAddress": "New Sale Point Address",
            "cropVariety": "New Crop Variety",
            "role": "JOINT_DIRECTOR"
        }
        
        with patch("apps.seed_licenses.views.write_to_contract", return_value={
            "success": True,
            "transaction_hash": "0x123abc"
        }):
            resp = client.post(reverse("update-license-details"), data=payload, format="json")
            assert resp.status_code == 202
            data = resp.json()["data"]
            assert "transaction_hash" in data
            assert data["status"] == "accepted"
    
    @pytest.mark.parametrize("payload,expected_error_fields,expected_messages", [
        ({"role": "JOINT_DIRECTOR"}, ["license_id"], ["This field is required."]),
        ({"license_id": 1}, ["role"], ["This field is required."]),
        (
            {"license_id": 1, "role": "INVALID_ROLE", "firm_name": "X"},
            ["role"],
            ["Invalid officer role string"]
        ),
        (
            {"license_id": 1, "role": "JOINT_DIRECTOR"},
            ["non_field_errors"],
            ["At least one field must be provided for update."]
        )
    ])
    def test_validation_fail(self, client, payload, expected_error_fields, expected_messages):
        resp = client.post(reverse("update-license-details"), data=payload, format="json")
        assert resp.status_code == 400
        
        error_data = resp.json().get("error", {})
        assert isinstance(error_data, dict)
        
        for field in expected_error_fields:
            assert field in error_data
        
        for msg in expected_messages:
            found = any(msg.lower() in str(err).lower() for err in error_data.values())
            assert found, f"Expected error message '{msg}' not found in {error_data}"
    
    def test_contract_failure(self, client):
        payload = {
            "licenseId": 1,
            "firmName": "New Firm Name",
            "firmType": "New Firm Type",
            "firmAddress": "New Firm Address",
            "salePointAddress": "New Sale Point Address",
            "cropVariety": "New Crop Variety",
            "role": "JOINT_DIRECTOR"
        }
        
        with patch("apps.seed_licenses.views.write_to_contract", return_value={
            "success": False,
            "error": "Transaction failed",
            "details": "Execution reverted (Only approved licenses can be edited)"
        }):
            resp = client.post(reverse("update-license-details"), data=payload, format="json")
            assert resp.status_code == 400
            data = resp.json()
            assert data.get("success") is False
            
            combined_error = str(data.get("data", "")).lower()
            assert "execution reverted" in combined_error
            assert "only approved licenses" in combined_error
    
    def test_exception_handling(self, client):
        payload = {
            "licenseId": 1,
            "firmName": "Updated Firm",
            "role": "JOINT_DIRECTOR",
        }
        
        with patch("apps.seed_licenses.views.write_to_contract", side_effect=Exception("Unexpected error")):
            resp = client.post(reverse("update-license-details"), data=payload, format="json")
            assert resp.status_code == 500
            err = resp.json().get("error", "")
            assert "Update license details failed" in err
            assert "Unexpected error" in err


# ============================================================================
# GET LICENSE QR DATA TESTS
# ============================================================================

@pytest.mark.django_db
class TestGetLicenseQRData:
    """Tests for license-qr-data endpoint"""
    
    def test_success(self, client):
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", return_value={
            "verificationHash": "90331eee50563f7f068f6f6ef25d99f3233aae1c67cb37dcfe981011d6f2fec0",
            "licenseNumber": "RJSDST2"
        }):
            resp = client.get(reverse("license-qr-data", args=[2]))
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["licenseNumber"] == "RJSDST2"
    
    @pytest.mark.parametrize("bad_license_id", ["abc", "12.3", "1a2"])
    def test_invalid_license_id(self, client, bad_license_id):
        resp = client.get(reverse("license-qr-data", args=[bad_license_id]))
        assert_error_contains(resp, "valid integer")
    
    @pytest.mark.parametrize("bad_license_id", [0, -1, -999])
    def test_negative_or_zero_license_id(self, client, bad_license_id):
        resp = client.get(reverse("license-qr-data", args=[bad_license_id]))
        assert_error_contains(resp, "positive integer")
    
    def test_contract_error(self, client):
        error_message = "Execution reverted (License must be active to generate QR data)"
        with patch("apps.seed_licenses.views.read_from_contract", side_effect=Exception(error_message)):
            resp = client.get(reverse("license-qr-data", args=[3]))
            err = resp.json().get("error", "")
            assert resp.status_code == 500
            assert "QR data fetch failed" in err
            assert error_message in err
    
    def test_unexpected_exception(self, client):
        with patch("apps.seed_licenses.views.read_from_contract", side_effect=Exception("Unexpected error")):
            resp = client.get(reverse("license-qr-data", args=[4]))
            err = resp.json().get("error", "")
            assert resp.status_code == 500
            assert "QR data fetch failed" in err
            assert "Unexpected error" in err


# ============================================================================
# MISCELLANEOUS TESTS
# ============================================================================

@pytest.mark.django_db
def test_contract_address(client):
    resp = client.get(reverse("contract-address"))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], str)


@pytest.mark.django_db
def test_transaction_status(client):
    resp = client.get(reverse("transaction-status", args=["0xabc"]))
    assert resp.status_code == 200
    assert "status" in resp.json()["data"]