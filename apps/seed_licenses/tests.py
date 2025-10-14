import base64
import pytest
from unittest.mock import patch 
from django.urls import reverse
from rest_framework import status
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
import apps.seed_licenses.services.blockchain as blockchain_service
# ✅ Import actual blockchain functions
from .services.blockchain import (
    write_to_contract,
    read_from_contract
)
from rest_framework.test import APIClient
import apps.seed_licenses.views as views_module 

from apps.seed_licenses.enums import LicenseStatusEnum
@pytest.fixture
def client():
    return APIClient()

@pytest.fixture(scope="session")
def public_key():
    return serialization.load_pem_public_key(settings.GENERATED_PUBLIC_KEY.encode("utf-8"))
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

def encrypt_aadhaar(public_key, aadhaar_plaintext="234567890123"):
    """
    Encrypt Aadhaar using RSA with OAEP (SHA-256), matching the backend decryption logic.
    """
    encrypted_bytes = public_key.encrypt(
        aadhaar_plaintext.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(encrypted_bytes).decode("utf-8")

@pytest.mark.django_db
def test_get_public_key(client):
    url = reverse("get-public-key")
    resp = client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "-----BEGIN PUBLIC KEY-----" in data["data"]
    
@pytest.mark.django_db
def test_check_owner_blockchain_success(client, monkeypatch):
    def mock_read_from_contract(method_name, params):
        assert method_name == "owner"
        assert params == []
        return "0xFE3B557E8Fb62b89F4916B721be55cEb828dBd73"

    monkeypatch.setattr(blockchain_service, "read_from_contract", mock_read_from_contract)
    url = reverse("check-owner")
    resp = client.get(url)

    assert resp.status_code == 200
    data = resp.json()
    assert data["data"] == "0xFE3B557E8Fb62b89F4916B721be55cEb828dBd73"
    
def test_check_owner_blockchain_value_error(client, monkeypatch):
    def mock_read_from_contract(method_name, params):
        raise ValueError("Method 'owner' not found")

    monkeypatch.setattr(views_module, "read_from_contract", mock_read_from_contract)

    url = reverse("check-owner")
    resp = client.get(url)

    assert resp.status_code == 400
    assert "Method 'owner' not found" in resp.json()["error"]
@pytest.mark.django_db
def test_check_owner_blockchain_unexpected_error(client, monkeypatch):
    def mock_read_from_contract(method_name, params):
        raise Exception("Blockchain node unreachable")
  
    monkeypatch.setattr(views_module, "read_from_contract", mock_read_from_contract)

    url = reverse("check-owner")
    resp = client.get(url)

    assert resp.status_code == 500
    data = resp.json()
    assert "Blockchain read failed" in data["error"]

@pytest.mark.django_db
def test_check_total_license_count_success(client):
    """
    Integration test hitting the real blockchain.
    Assumes licenseIdCounter is defined in the smart contract.
    """
    url = reverse("license-count")
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert isinstance(data["data"], int)
    assert data["data"] >= 0
    


@pytest.mark.django_db
def test_check_total_license_count_invalid_method(monkeypatch, client):
    def mock_read_from_contract(method_name, params):
        raise ValueError("Method 'licenseIdCounter' not found")

    monkeypatch.setattr(views_module, "read_from_contract", mock_read_from_contract)

    url = reverse("license-count")
    response = client.get(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "licenseIdCounter" in data["error"]


@pytest.mark.django_db
def test_check_total_license_count_node_down(monkeypatch, client):
    def mock_read_from_contract(method_name, params):
        raise Exception("Connection error: Blockchain node unreachable")

    monkeypatch.setattr(views_module, "read_from_contract", mock_read_from_contract)

    url = reverse("license-count")
    response = client.get(url)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = response.json()
    assert "Blockchain write failed" in data["error"]


@pytest.mark.django_db
def test_check_total_license_count_unexpected_error(monkeypatch, client):
    def mock_read_from_contract(method_name, params):
        raise Exception("Timeout while reading from blockchain")

    monkeypatch.setattr(views_module, "read_from_contract", mock_read_from_contract)

    url = reverse("license-count")
    response = client.get(url)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = response.json()
    assert "Blockchain write failed" in data["error"]



@pytest.mark.django_db
def test_submit_license_application_success(client, public_key):
    url = reverse("submit-license-application")
    payload = {
     "licenseCategory": "SEED",
        "licenseLevel": "DISTRICT",
        "registeringAuthority": "Govt",
        "registeringOfficeName": "Dept",
        "applicantName": "Alice",
        "aadhaarNumber": encrypt_aadhaar(public_key, "234567890123"),
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

    response = client.post(url, data=payload, format="json")
    assert response.status_code == status.HTTP_202_ACCEPTED
    data=response.json()
    assert "transaction_hash" in data["data"]

    
@pytest.mark.django_db
def test_submit_license_application_invalid_input(client):
    url = reverse("submit-license-application")
    payload = {
        # intentionally leaving required fields like 'license_category'
        "applicantName": "Alice"
    }
    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    data = resp.json()
    assert "license_category" in data.get("error",'')

@pytest.mark.django_db
def test_submit_license_application_blockchain_failure(monkeypatch, client, public_key):
    def mock_write_to_contract(method_name, params, *args, **kwargs):
        return {"success": False, "error": "Contract rejected transaction"}

    monkeypatch.setattr(views_module, "write_to_contract", mock_write_to_contract)

    url = reverse("submit-license-application")
    payload = {
         "licenseCategory": "SEED",
        "licenseLevel": "DISTRICT",
        "registeringAuthority": "Govt",
        "registeringOfficeName": "Dept",
        "applicantName": "Alice",
        "aadhaarNumber": encrypt_aadhaar(public_key, "123412341234"),
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

    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    data = resp.json()
    assert "error" not in data.get("error") or "Contract rejected" in str(data.get("error",''))
    from unittest.mock import patch
import pytest
from rest_framework import status
from django.urls import reverse

@pytest.mark.django_db
def test_submit_license_application_exception(client, public_key):
    url = reverse("submit-license-application")

    payload = {
        "licenseCategory": "SEED",
        "licenseLevel": "DISTRICT",
        "registeringAuthority": "Govt",
        "registeringOfficeName": "Dept",
        "applicantName": "Alice",
        "aadhaarNumber": encrypt_aadhaar(public_key, "234567890123"),
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

    with patch("apps.seed_licenses.views.write_to_contract") as mock_write:
        mock_write.side_effect = Exception("Node connection failed")

        resp = client.post(url, data=payload, format="json")

        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = resp.json()
        assert "Create license failed" in data.get("error")

@pytest.mark.django_db
def test_get_license_basic_info_success(client):
    url = reverse("license-basic-info", args=[1])
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK

    resp_json = response.json()

    # ✅ Top-level keys
    assert "success" in resp_json
    assert resp_json["success"] is True
    assert "data" in resp_json

    # ✅ License detail keys
    license_data = resp_json["data"]
    expected_keys = {
        "licenseId", "licenseNumber", "applicantName", "category", "level", "status",
        "firmName", "firmType", "firmAddress", "salePointAddress", "saleStorageAddress",
        "productionCompany", "cropName", "cropVariety", "registeringOfficeName",
        "registeringAuthority", "applicationDate", "expiryDate", "isActive"
    }

    missing_keys = expected_keys - license_data.keys()
    assert not missing_keys, f"Missing keys in response: {missing_keys}"

@pytest.mark.django_db
def test_get_license_basic_info_non_integer_id(client):
    url = reverse("license-basic-info", args=["abc"])
    response = client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "License ID must be a valid integer" in data.get("error", "")
    
@pytest.mark.django_db
def test_get_license_basic_info_negative_id(client):
    url = reverse("license-basic-info", args=[-5])
    response = client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "License ID must be positive integer" in data.get("error", "")


@pytest.mark.django_db
def test_get_license_basic_info_blockchain_failure(monkeypatch, client):
    def mock_read_from_contract(*args, **kwargs):
        raise Exception("Blockchain unreachable")

    monkeypatch.setattr(views_module, "read_from_contract", mock_read_from_contract)

    url = reverse("license-basic-info", args=[1])
    response = client.get(url)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = response.json()
    assert "License information unavailable" in data.get("error", "")


@pytest.mark.django_db
def test_update_license_status_success(client):
    license_id = 1
    payload = {
        "licenseId": license_id,
        "status": "UNDER_REVIEW",
        "officerName": "Bob",
        "role": "AGRICULTURE_OFFICER",
        "renewalPeriodDays": 34,
        "remarks": "License is under review"
    }

    with patch("apps.seed_licenses.views.read_from_contract") as mock_read, \
         patch("apps.seed_licenses.views.write_to_contract") as mock_write:

        mock_read.return_value = {"status": "SUBMITTED"}

        mock_write.return_value = {
            "success": True,
            "data": {
                "transaction_hash": "0xabc123",
                "status": "accepted",
                "message": "Transaction submitted successfully. Processing will continue in the background."
            }
        }

        url = reverse("update-license-status")
        response = client.post(url, data=payload, format="json")

        print("Response JSON:", response.json())

        assert response.status_code == 202
        resp_data = response.json()
        assert resp_data["data"]["status"] == "accepted"       
        assert resp_data["success"] is True
     
        assert "Transaction submitted" in resp_data["data"]["message"]
        
@pytest.mark.django_db
def test_update_license_status_invalid_transition(monkeypatch, client):
    monkeypatch.setattr(
        views_module, "write_to_contract",
        lambda *args, **kwargs: {"status": "UNDER_REVIEW"}
    )

    url = reverse("update-license-status")
    payload = {
        "licenseId": 1,
        "status": "APPROVED",  # Not valid directly from UNDER_REVIEW
        "officerName": "Shrawan",
        "role": "AGRICULTURE_OFFICER",
        "remarks": "Trying invalid transition",
        "renewalPeriodDays": 34
    }

    response = client.post(url, data=payload, format="json")
    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["error"]

@pytest.mark.django_db
def test_update_license_status_missing_renewal_period(client):
    url = reverse("update-license-status")
    payload = {
        "licenseId": 1,
        "status": "APPROVED",
        "officerName": "Shrawan",
        "role": "AGRICULTURE_OFFICER",
        "remarks": "Missing renewal period"
    }

    response = client.post(url, data=payload, format="json")
    assert response.status_code == 400
    assert "renewal_period_days" in response.json()["error"]


@pytest.mark.django_db
def test_update_license_status_invalid_status_value(client):
    url = reverse("update-license-status")
    payload = {
        "licenseId": 1,
        "status": "INVALID_STATUS",
        "officerName": "Bob",
        "role": "AGRICULTURE_OFFICER",
        "remarks": "Invalid status test"
    }

    response = client.post(url, data=payload, format="json")
    assert response.status_code == 400
    assert "Invalid license status" in str(response.json()["error"])

@pytest.mark.django_db
def test_update_license_status_blockchain_write_failed(monkeypatch, client):
    monkeypatch.setattr(
     views_module, "write_to_contract",
        lambda *args, **kwargs: {      "success": False,
            "error": "Reverted by EVM"}
    )

    monkeypatch.setattr(
        views_module, "write_to_contract",
        lambda *args, **kwargs: {
            "success": False,
            "error": "Reverted by EVM"
        }
    )

    url = reverse("update-license-status")
    payload = {
        "licenseId": 1,
        "status": "UNDER_REVIEW",
        "officerName": "Bob",
        "role": "AGRICULTURE_OFFICER",
        "remarks": "Blockchain rejection"
    }

    response = client.post(url, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_update_license_status_unexpected_error(client):
    url = reverse("update-license-status")
    payload = {
      "licenseId":2,
 "status":"APPROVED",
 "officerName": "Shrawan",
 "role": "AGRICULTURE_OFFICER",
 "renewalPeriodDays": 34,
 "remarks":"License is UNDER_REVIEW"
    }

    with patch("apps.seed_licenses.views.read_from_contract") as mock_read, \
         patch("apps.seed_licenses.views.write_to_contract") as mock_write:

        # Mock read_from_contract to return current license info
        mock_read.return_value = {
            "status": "APPLIED"  # or any valid current status string expected by LicenseStatusEnum.from_string
        }

        # Mock write_to_contract to raise an exception
        mock_write.side_effect = ZeroDivisionError("division by zero")

        response = client.post(url, data=payload, format="json")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Update license status failed" in response.json().get("error", "")


@pytest.mark.django_db
@pytest.mark.parametrize("field, value", [("officer_name", ""), ("remarks", "")])
def test_update_license_status_empty_fields(client, field, value):
    payload = {
        "licenseId": 1,
        "status": "UNDER_REVIEW",
        "officerName": "Bob",
        "role": "AGRICULTURE_OFFICER",
        "remarks": "Reasonable"
    }
    payload[field] = value

    url = reverse("update-license-status")
    response = client.post(url, data=payload, format="json")
    assert response.status_code == 400
    assert field in response.json()["error"]

@pytest.mark.django_db
def test_verify_license_document_success(monkeypatch, client):
    monkeypatch.setattr(
        views_module, "write_to_contract",
        lambda *args, **kwargs: {
            "success": True,
            "transaction_hash": "0xabc123"
        }
    )

    url = reverse("verify-license-document")
    payload = {
        "licenseNumber": "RJSDST2",
        "expectedHash": "abcdef"
    }

    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["status"] == "accepted"
    assert "transaction_hash" in data

@pytest.mark.django_db
def test_verify_license_document_missing_license_number(client):
    url = reverse("verify-license-document")
    payload = {
        "licenseNumber": "",
        "expectedHash": "abcdef"
    }

    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == 400

    assert resp.json()["error"] == {
    "license_number": ["This field may not be blank."]
}


@pytest.mark.django_db
def test_verify_license_document_missing_expected_hash(client):
    url = reverse("verify-license-document")
    payload = {
        "licenseNumber": "LIC123",
        "expectedHash": ""
    }

    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == 400
    assert resp.json()["error"] == {
    "expected_hash": ["This field may not be blank."]
}

@pytest.mark.django_db
def test_verify_license_document_blockchain_fail(monkeypatch, client):
    monkeypatch.setattr(
        views_module, "write_to_contract",
        lambda *args, **kwargs: {
            "success": False,
            "error": "Transaction failed",
            "details": "Execution reverted (License application is under review)"
        }
    )

    url = reverse("verify-license-document")
    payload = {
        "licenseNumber": "LIC123",
        "expectedHash": "abcdef"
    }

    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == 400
    data = resp.json()["data"]
    assert data["success"] is False
    assert "Transaction failed" in data["error"]

@pytest.mark.django_db
def test_verify_license_document_unexpected_exception(monkeypatch, client):
    def raise_error(*args, **kwargs):
        raise RuntimeError("Unexpected failure")

    monkeypatch.setattr(views_module, "write_to_contract", raise_error)

    url = reverse("verify-license-document")
    payload = {
        "licenseNumber": "LIC123",
        "expectedHash": "abcdef"
    }

    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == 500
    assert "Verify document failed" in resp.json()["error"]



@pytest.mark.django_db
def test_get_license_action_history_success(client):
    # Mock read_from_contract to return valid data
    with patch("apps.seed_licenses.services.blockchain.read_from_contract") as mock_read:
        mock_read.return_value = [
            {
                "timestamp": "14 October 2025",
                "actionType": "SUBMITTED",
                "actorName": "Ravi Kumar",
                "actorRole": "CITIZEN",
                "remarks": "License Application Successfully Submitted",
                "dataHash": "14fc6f02faff112e3cb4b6f2df0ce53e9a628639cea9c03bc751f2df285bc1e8"
            }
        ]

        url = reverse("license-action-history", args=[1])
        resp = client.get(url)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert data[0]["actionType"] == "SUBMITTED"


@pytest.mark.django_db
def test_get_license_action_history_invalid_license_id_non_integer(client):
    url = reverse("license-action-history", args=["abc"])
    resp = client.get(url)
    assert resp.status_code == 400
    assert "License ID must be a valid integer" in resp.json()["error"]


@pytest.mark.django_db
def test_get_license_action_history_invalid_license_id_negative(client):
    url = reverse("license-action-history", args=[-5])
    resp = client.get(url)
    assert resp.status_code == 400
    assert "License ID must be positive integer" in resp.json()["error"]


@pytest.mark.django_db
def test_get_license_action_history_value_error_from_contract(client):
    # Simulate ValueError from read_from_contract (bad license id or similar)
    with patch("apps.seed_licenses.views.read_from_contract") as mock_read:
        mock_read.side_effect = ValueError("License ID does not exist")

        url = reverse("license-action-history", args=[999])
        resp = client.get(url)
        assert resp.status_code == 400
        assert "License ID does not exist" in resp.json()["error"]


@pytest.mark.django_db
def test_get_license_action_history_unexpected_exception(client):
    # Simulate generic exception from read_from_contract
    with patch("apps.seed_licenses.views.read_from_contract") as mock_read:
        mock_read.side_effect = Exception("Unexpected failure")

        url = reverse("license-action-history", args=[1])
        resp = client.get(url)
        assert resp.status_code == 500
        assert "Blockchain write failed" in resp.json()["error"]



@pytest.mark.django_db
def test_update_license_details_success(client):
    """ Success: valid payload and contract returns success """
    url = reverse("update-license-details")
    payload = {
    "license_id": 1,
    "firm_name": "New Firm Name",
    "firm_type": "New Firm Type",
    "firm_address": "New Firm Address",
    "sale_point_address": "New Sale Point Address",
    "crop_variety": "New Crop Variety",
    "role": "JOINT_DIRECTOR"
    }
    mock_result = {
        "success": True,
        "transaction_hash": "0x123abc"
    }
    with patch("apps.seed_licenses.views.write_to_contract") as mock_write:
        mock_write.return_value = mock_result
        resp = client.post(url, data=payload, format="json")
        assert resp.status_code == 202
        data = resp.json().get("data", {})
        assert "transaction_hash" in data
        assert data["status"] == "accepted"

@pytest.mark.django_db
@pytest.mark.parametrize("payload, expected_error_fields, expected_messages", [
    ({"role": "JOINT_DIRECTOR"}, ["license_id"], ["This field is required."]),  # Missing license_id
    ({"license_id": 1}, ["role"], ["This field is required."]),                # Missing role
    (
        {"license_id": 1, "role": "INVALID_ROLE", "firm_name": "X"},
        ["role"],
        ["Invalid officer role string"]
    ),  # Invalid role
    (
        {"license_id": 1, "role": "JOINT_DIRECTOR"},
        ["non_field_errors"],
        ["At least one field must be provided for update."]
    )  # No update fields
])
def test_update_license_details_validation_fail(client, payload, expected_error_fields, expected_messages):
    url = reverse("update-license-details")
    resp = client.post(url, data=payload, format="json")
    assert resp.status_code == 400

    error_data = resp.json().get("error", {})
    assert isinstance(error_data, dict)

    for field in expected_error_fields:
        assert field in error_data

    for msg in expected_messages:
        found = any(msg.lower() in str(err).lower() for err in error_data.values())
        assert found, f"Expected error message '{msg}' not found in {error_data}"

@pytest.mark.django_db
def test_update_license_details_contract_failure(client):
    url = reverse("update-license-details")
    payload = {
    "license_id": 1,
    "firm_name": "New Firm Name",
    "firm_type": "New Firm Type",
    "firm_address": "New Firm Address",
    "sale_point_address": "New Sale Point Address",
    "crop_variety": "New Crop Variety",
    "role": "JOINT_DIRECTOR"
    }

    mock_result = {
        "success": False,
        "error": "Transaction failed",
        "details": "Execution reverted (Only approved licenses can be edited)"
    }

    with patch("apps.seed_licenses.views.write_to_contract") as mock_write:
        mock_write.return_value = mock_result

        resp = client.post(url, data=payload, format="json")
        assert resp.status_code == 400
        data = resp.json()

        print("DEBUG RESPONSE:", data)

        assert data.get("success") is False

        # Combine everything for easier fuzzy match
        combined_error = str(data.get("data", "")).lower()
        assert "execution reverted" in combined_error
        assert "only approved licenses" in combined_error



@pytest.mark.django_db
def test_update_license_details_exception_handling(client):
    """ Unexpected exception during contract call """
    url = reverse("update-license-details")
    payload = {
        "license_id": 1,
        "firm_name": "Updated Firm",
        "role": "JOINT_DIRECTOR",
    }
    with patch("apps.seed_licenses.views.write_to_contract") as mock_write:
        mock_write.side_effect = Exception("Unexpected error")
        resp = client.post(url, data=payload, format="json")
        assert resp.status_code == 500
        err = resp.json().get("error", "")
        assert "Update license details failed" in err
        assert "Unexpected error" in err



@pytest.mark.django_db
def test_get_license_qr_data_success(client):
    """ Success: valid license_id returns QR data """
    license_id = 2
    mock_response = {
        "verificationHash": "90331eee50563f7f068f6f6ef25d99f3233aae1c67cb37dcfe981011d6f2fec0",
        "licenseNumber": "RJSDST2"
    }
    with patch("apps.seed_licenses.services.blockchain.read_from_contract") as mock_read:
        mock_read.return_value = mock_response
        url = reverse("license-qr-data", args=[license_id])
        resp = client.get(url)
        assert resp.status_code == 200
        data = resp.json().get("data", {})
        assert "licenseNumber" in data
        assert data["licenseNumber"] == "RJSDST2"


@pytest.mark.django_db
@pytest.mark.parametrize("bad_license_id", ["abc", "12.3", "1a2"])
def test_get_license_qr_data_failure_invalid_license_id(client, bad_license_id):
    """ Failure: license_id is not a valid integer """
    url = reverse("license-qr-data", args=[bad_license_id])
    resp = client.get(url)
    assert resp.status_code == 400
    assert "valid integer" in resp.json().get("error", "").lower()


@pytest.mark.django_db
@pytest.mark.parametrize("bad_license_id", [0, -1, -999])
def test_get_license_qr_data_failure_negative_or_zero_license_id(client, bad_license_id):
    """ Failure: license_id <= 0 """
    url = reverse("license-qr-data", args=[bad_license_id])
    resp = client.get(url)
    assert resp.status_code == 400
    assert "positive integer" in resp.json().get("error", "").lower()


@pytest.mark.django_db
def test_get_license_qr_data_failure_contract_error(client):
    """ Failure: contract returns error (e.g., license not active) """
    license_id = 3
    error_message = "Execution reverted (License must be active to generate QR data)"
    with patch("apps.seed_licenses.views.read_from_contract") as mock_read:
        mock_read.side_effect = Exception(error_message)
        url = reverse("license-qr-data", args=[license_id])
        resp = client.get(url)
        assert resp.status_code == 500
        err = resp.json().get("error", "")
        assert "QR data fetch failed" in err
        assert error_message in err


@pytest.mark.django_db
def test_get_license_qr_data_failure_unexpected_exception(client):
    """ Failure: unexpected exception during contract read """
    license_id = 4
    with patch("apps.seed_licenses.views.read_from_contract") as mock_read:
        mock_read.side_effect = Exception("Unexpected error")
        url = reverse("license-qr-data", args=[license_id])
        resp = client.get(url)
        assert resp.status_code == 500
        err = resp.json().get("error", "")
        assert "QR data fetch failed" in err
        assert "Unexpected error" in err


@pytest.mark.django_db
def test_contract_address(client):
    url = reverse("contract-address")
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["data"], str)



@pytest.mark.django_db
def test_transaction_status(client):
    url = reverse("transaction-status", args=["0xabc"])
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data["data"]
