"""
Integration tests for overall system state management
"""
import pytest
import json
from unittest.mock import patch
from django.urls import reverse
from apps.seed_licenses.tests.integration.fixtures import blockchain_state, complete_license_payload
from apps.seed_licenses.tests.conftest import client


@pytest.mark.django_db
class TestSystemState:
    """Test overall system state management"""
    
    def test_system_info_endpoints(self, client, blockchain_state):
        """Test system information endpoints"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract):
            
            # Check owner
            resp = client.get(reverse("check-owner"))
            assert resp.status_code == 200
            assert resp.json()["data"].startswith("0x")
            
            # Check contract address
            resp = client.get(reverse("contract-address"))
            assert resp.status_code == 200
            assert isinstance(resp.json()["data"], str)
    
    def test_public_key_endpoint(self, client):
        """Test public key retrieval"""
        resp = client.get(reverse("get-public-key"))
        assert resp.status_code == 200
        assert "BEGIN PUBLIC KEY" in resp.json()["data"]
    
    def test_license_count_accuracy(self, client, complete_license_payload, blockchain_state):
        """Test that license count accurately reflects system state"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Initial count should be 0
            resp = client.get(reverse("license-count"))
            assert resp.json()["data"] == {}
            
            # Create 3 licenses
            for i in range(3):
                payload = complete_license_payload.copy()
                payload.pop("applicantName", None)
                payload["applicantName"] = f"Applicant {i+1}"
                resp=client.post(
                    reverse("submit-license-application"),
                    data=json.dumps(payload),
                    content_type='application/json'
                )
                print("🔹 Submitted license:", resp.json())
            # Count should be 3
            resp = client.get(reverse("license-count"))
            print("🔹 License count after 3 submissions:", resp.json())
            assert resp.json()["data"] == 3
            
            # Change statuses (shouldn't affect count)
            client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": 1,
                    "status": "UNDER_REVIEW",
                    "officerName": "Officer",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Review"
                },
                content_type='application/json'
            )
            
            client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": 2,
                    "status": "UNDER_REVIEW",
                    "officerName": "Officer",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Review"
                },
                content_type='application/json'
            )
            
            client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": 2,
                    "status": "REJECTED",
                    "officerName": "Director",
                    "role": "JOINT_DIRECTOR",
                    "remarks": "Rejected"
                },
                content_type='application/json'
            )
            
            # Count should still be 3
            resp = client.get(reverse("license-count"))
            assert resp.json()["data"] == 3
    
    def test_system_state_after_multiple_operations(self, client, complete_license_payload, blockchain_state):
        """Test system state remains consistent after multiple operations"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create licenses
            for i in range(5):
                payload = complete_license_payload.copy()
                payload["applicantName"] = f"Applicant {i+1}"
                resp=client.post(
                    reverse("submit-license-application"),
                    data=json.dumps(payload),
                    content_type='application/json'
                )
                print("🔹 Submitted license:", resp.json())
            
            # Perform various operations
            operations_count = 0
            
            # Update some licenses
            for license_id in [1, 2, 3]:
                client.post(
                    reverse("update-license-status"),
                    data=json.dumps({
                        "licenseId": license_id,
                        "status": "UNDER_REVIEW",
                        "officerName": "Officer",
                        "role": "AGRICULTURE_OFFICER",
                        "remarks": "Review"
                    }),
                    content_type='application/json'
                )
                operations_count += 1
            
            # Read some licenses
            for license_id in [1, 2, 3, 4, 5]:
                client.get(reverse("license-basic-info", args=[license_id]))
                operations_count += 1
            
            # Get QR data
            for license_id in [1, 2]:
                client.get(reverse("license-qr-data", args=[license_id]))
                operations_count += 1
            
            # Verify system state
            resp = client.get(reverse("license-count"))
            assert resp.json()["data"] == 5
            
            # Verify all licenses still accessible
            for license_id in range(1, 6):
                resp = client.get(reverse("license-basic-info", args=[license_id]))
                assert resp.status_code == 200
    
    def test_system_endpoints_without_licenses(self, client, blockchain_state):
        """Test system endpoints work even without any licenses"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract):
            
            # All system endpoints should work
            resp = client.get(reverse("check-owner"))
            print("🔹 Check owner response:", resp.json())
            assert resp.status_code == 200
            
            resp = client.get(reverse("contract-address"))
            print("🔹 Contract address response:", resp.json())
            assert resp.status_code == 200
            
            resp = client.get(reverse("get-public-key"))
            print("🔹 Public key response:", resp.json())
            assert resp.status_code == 200
            
            resp = client.get(reverse("license-count"))
            assert resp.status_code == 200
            print("🔹 License count response:", resp.json())
            assert resp.json()["data"] == {}