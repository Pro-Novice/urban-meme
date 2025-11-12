"""
Integration tests for concurrent operations on licenses
"""
import pytest
import json
from unittest.mock import patch
from django.urls import reverse
from apps.seed_licenses.tests.integration.fixtures import blockchain_state, complete_license_payload
from apps.seed_licenses.tests.conftest import client


@pytest.mark.django_db
class TestConcurrentOperations:
    """Test concurrent operations on licenses"""
    
    def test_parallel_license_submissions(self, client, complete_license_payload, blockchain_state):
        """Test submitting multiple licenses in parallel"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Submit 5 licenses rapidly
            responses = []
            for i in range(5):
                payload = complete_license_payload.copy()
                payload.pop("applicantName", None)
                payload["applicantName"] = f"Applicant {i+1}"
                
                resp = client.post(
                    reverse("submit-license-application"),
                    data=json.dumps(payload),
                    content_type='application/json'
                )
                responses.append(resp)
            
            # All should succeed
            for resp in responses:
                assert resp.status_code == 202
            
            # Verify final count
            resp = client.get(reverse("license-count"))
            assert resp.json()["data"] == 5
            
            # Verify each license exists
            for i in range(1, 6):
                resp = client.get(reverse("license-basic-info", args=[i]))
                assert resp.status_code == 200
                assert resp.json()["data"]["licenseId"] == i
    
    def test_rapid_status_updates_same_license(self, client, complete_license_payload, blockchain_state):
        """Test rapid status updates on the same license"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            client.post(
                reverse("submit-license-application"),
                data=json.dumps(complete_license_payload),
                content_type='application/json'
            )
            license_id = 1
            
            # Perform rapid sequential updates
            statuses = [
                "UNDER_REVIEW",
                "DOCUMENTS_VERIFIED",
                "INSPECTION_SCHEDULED",
                "INSPECTION_COMPLETED"
            ]
            
            for status in statuses:
                resp = client.post(
                    reverse("update-license-status"),
                    data=json.dumps({
                        "licenseId": license_id,
                        "status": status,
                        "officerName": "Officer",
                        "role": "AGRICULTURE_OFFICER",
                        "remarks": f"Update to {status}"
                    }),
                    content_type='application/json'
                )
                print(f"Updated to {status}, Status Code: {resp.status_code}, Response: {resp.json()}") 
                assert resp.status_code == 202
            
            # Verify final status
            resp = client.get(reverse("license-basic-info", args=[license_id]))
            assert resp.json()["data"]["status"] == "INSPECTION COMPLETED"
            
            # Verify action history count
            resp = client.get(reverse("license-action-history", args=[license_id]))
            history = resp.json()["data"]
            assert len(history) == len(statuses) + 1  # +1 for SUBMITTED
    
    def test_multiple_licenses_different_operations(self, client, complete_license_payload, blockchain_state):
        """Test different operations on multiple licenses simultaneously"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create 3 licenses
            for i in range(3):
                payload = complete_license_payload.copy()
                payload["applicantName"] = f"Applicant {i+1}"
                client.post(
                    reverse("submit-license-application"),
                    data=json.dumps(payload),
                    content_type='application/json'
                )
            
            # Perform different operations simultaneously
            # License 1: Update status
            resp1 = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": 1,
                    "status": "UNDER_REVIEW",
                    "officerName": "Officer A",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Review 1"
                }),
                content_type='application/json'
            )
            print("🔹 License 1 Update Response:", resp1.status_code, resp1.json())
            # License 2: Get basic info
            resp2 = client.get(reverse("license-basic-info", args=[2]))
            print("🔹 License 2 Info Response:", resp2.status_code, resp2.json())
            # License 3: Get QR data
            resp3 = client.get(reverse("license-qr-data", args=[3]))
            print("🔹 License 3 QR Data Response:", resp3.status_code, resp3.json())
            # All operations should succeed
            assert resp1.status_code == 202
            assert resp2.status_code == 200
            assert resp3.status_code == 200
    
    def test_concurrent_reads_during_update(self, client, complete_license_payload, blockchain_state):
        """Test reading license data while updates are happening"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            resp1=client.post(
                reverse("submit-license-application"),
                data=json.dumps(complete_license_payload),
                content_type='application/json'
            )
            license_id = 1
            print("🔹 License Creation Response:", resp1.status_code, resp1.json())
            # Update status
            resp2=client.post(
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
            print("🔹 License Update Response:", resp2.status_code, resp2.json())
            
            # Perform multiple reads
            responses = []
            for _ in range(5):
                resp = client.get(reverse("license-basic-info", args=[license_id]))
                print("🔹 License Read Response:", resp.status_code, resp.json())
                responses.append(resp)
            
            # All reads should succeed
            for resp in responses:
                assert resp.status_code == 200
                assert resp.json()["data"]["status"] == "UNDER REVIEW"