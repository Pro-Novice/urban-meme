"""
Integration tests for complete license lifecycle workflows
"""
import pytest
import json
from unittest.mock import patch
from django.urls import reverse
from apps.seed_licenses.tests.integration.fixtures import blockchain_state, complete_license_payload
from apps.seed_licenses.tests.conftest import client


@pytest.mark.django_db
class TestCompleteLicenseLifecycle:
    """Test the complete workflow from application to approval"""
    
    def test_full_license_workflow(self, client, complete_license_payload, blockchain_state):
        """Test complete license lifecycle: Submit -> Review -> Verify -> Approve"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Step 1: Check initial license count
            resp = client.get(reverse("license-count"))
            assert resp.status_code == 200
            initial_count = resp.json()["data"]
            assert initial_count == {}
            
            # Step 2: Submit license application
            resp = client.post(
                reverse("submit-license-application"),
                data=json.dumps(complete_license_payload),
                content_type='application/json'
            )
            print("🔹 Payload sent:", complete_license_payload)
            print("🔹 Status code:", resp.status_code)
            print("🔹 Response JSON:", resp.json())
            assert resp.status_code == 202
            tx_hash = resp.json()["data"]["transaction_hash"]
            assert tx_hash.startswith("0xtx")
            
            # Step 3: Verify license count increased
            resp = client.get(reverse("license-count"))
            assert resp.status_code == 200
            assert resp.json()["data"] == 1
            
            # Step 4: Get license basic info
            license_id = 1
            resp = client.get(reverse("license-basic-info", args=[license_id]))
            assert resp.status_code == 200
            license_data = resp.json()["data"]
            assert license_data["status"] == "SUBMITTED"
            assert license_data["applicantName"] == "Rajesh Kumar"
            assert license_data["firmName"] == "Kumar Seeds Pvt Ltd"
            
            # Step 5: Update status to UNDER_REVIEW
            resp = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": license_id,
                    "status": "UNDER_REVIEW",
                    "officerName": "Inspector Singh",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Initial review started"
                }),
                content_type='application/json' 
            )
            assert resp.status_code == 202
            
            # Step 6: Verify status changed
            resp = client.get(reverse("license-basic-info", args=[license_id]))
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "UNDER REVIEW"
            
            # Step 7: Check action history
            resp = client.get(reverse("license-action-history", args=[license_id]))
            assert resp.status_code == 200
            history = resp.json()["data"]
            assert len(history) == 2
            assert history[0]["actionType"] == "SUBMITTED"
            assert history[1]["actionType"] == "UNDER_REVIEW"
            
            # Step 8: Update to DOCUMENTS_VERIFIED
            resp = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": license_id,
                    "status": "DOCUMENTS_VERIFIED",
                    "officerName": "Verifier Sharma",
                    "role": "DEPUTY_DIRECTOR",
                    "remarks": "All documents verified successfully"
                }),
                content_type='application/json'
            )
            assert resp.status_code == 202
            
            # Step 9: Schedule inspection
            resp = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": license_id,
                    "status": "INSPECTION_SCHEDULED",
                    "officerName": "Inspector Patel",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Inspection scheduled for next week"
                }),
                content_type='application/json'
            )
            assert resp.status_code == 202
            
            # Step 10: Complete inspection
            resp = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": license_id,
                    "status": "INSPECTION_COMPLETED",
                    "officerName": "Inspector Patel",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Inspection completed successfully"
                }),
                content_type='application/json'
            )
            assert resp.status_code == 202
            
            # Step 11: Approve license
            resp = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": license_id,
                    "status": "APPROVED",
                    "officerName": "Director Kumar",
                    "role": "JOINT_DIRECTOR",
                    "remarks": "License approved",
                    "renewalPeriodDays": 365
                }),
                content_type='application/json'
            )
            assert resp.status_code == 202
            
            # Step 12: Verify final status
            resp = client.get(reverse("license-basic-info", args=[license_id]))
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "APPROVED"
            
            # Step 13: Check complete action history
            resp = client.get(reverse("license-action-history", args=[license_id]))
            assert resp.status_code == 200
            history = resp.json()["data"]
            assert len(history) == 6
            
            expected_statuses = [
                "SUBMITTED", "UNDER_REVIEW", "DOCUMENTS_VERIFIED",
                "INSPECTION_SCHEDULED", "INSPECTION_COMPLETED", "APPROVED"
            ]
            for i, expected_status in enumerate(expected_statuses):
                assert history[i]["actionType"] == expected_status
    
    def test_license_rejection_workflow(self, client, complete_license_payload, blockchain_state):
        """Test license rejection during review"""
        
        # Reset state at the start
        blockchain_state.reset()
        print("Initial blockchain state - counter:", blockchain_state.counter)
        print("Initial blockchain state - licenses:", blockchain_state.licenses)
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Submit application
            resp = client.post(
                reverse("submit-license-application"),
                data=json.dumps(complete_license_payload),
                content_type='application/json'
            )
            print("🔹 Submit - Status code:", resp.status_code)
            print("🔹 Submit - Response JSON:", resp.json())
            print("🔹 Blockchain state after submission - counter:", blockchain_state.counter)
            print("🔹 Blockchain state after submission - licenses:", blockchain_state.licenses)
            
            assert resp.status_code == 202
            license_id = 1
            
            # Move to under review
            resp = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": license_id,
                    "status": "UNDER_REVIEW",
                    "officerName": "Inspector Singh",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Starting review"
                }),
                content_type='application/json'
            )
            print("🔹 Under Review - Status code:", resp.status_code)
            print("🔹 Under Review - Response JSON:", resp.json())
            assert resp.status_code == 202

            # Reject the license
            resp = client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": license_id,
                    "status": "REJECTED",
                    "officerName": "Director Patel",
                    "role": "JOINT_DIRECTOR",
                    "remarks": "Incomplete documentation"
                }),
                content_type='application/json'
            )
            print("🔹 Rejection - Status code:", resp.status_code)
            print("🔹 Rejection - Response JSON:", resp.json())
            assert resp.status_code == 202
            
            # Verify rejection
            resp = client.get(reverse("license-basic-info", args=[license_id]))
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "REJECTED"