"""
Integration tests for handling multiple licenses simultaneously
"""
import pytest
import json
from unittest.mock import patch
from django.urls import reverse
from apps.seed_licenses.tests.integration.fixtures import blockchain_state, complete_license_payload
from apps.seed_licenses.tests.conftest import client


@pytest.mark.django_db
class TestMultipleLicenses:
    """Test handling multiple licenses simultaneously"""
    
    def test_multiple_licenses_creation(self, client, complete_license_payload, blockchain_state):
        """Test creating and managing multiple licenses"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create 3 licenses
            license_ids = []
            for i in range(3):
                payload = complete_license_payload.copy()
                payload["applicantName"] = f"Applicant {i+1}"
                payload["firmName"] = f"Firm {i+1}"
                
                resp = client.post(
                    reverse("submit-license-application"),
                    data=json.dumps(payload),
                    content_type='application/json'
                )
                print(f"🔹 License {i+1} Creation Response:", resp.status_code, resp.json())
                assert resp.status_code == 202
                license_ids.append(i + 1)
            
            # Verify count
            resp = client.get(reverse("license-count"))
            assert resp.status_code == 200
            assert resp.json()["data"] == 3
            
            # Process each license differently
            # License 1: Move to UNDER_REVIEW
            client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": 1,
                    "status": "UNDER_REVIEW",
                    "officerName": "Officer A",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Review started"
                }),
                content_type='application/json'
            )
            
            # License 2: Reject during review
            client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": 2,
                    "status": "UNDER_REVIEW",
                    "officerName": "Officer B",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Review started"
                }),
                content_type='application/json'
            )
            client.post(
                reverse("update-license-status"),
                data=json.dumps({
                    "licenseId": 2,
                    "status": "REJECTED",
                    "officerName": "Director",
                    "role": "JOINT_DIRECTOR",
                    "remarks": "Rejected"
                }),
                content_type='application/json'
            )
            
            # License 3: Keep in submitted state
            
            # Verify statuses
            resp = client.get(reverse("license-basic-info", args=[1]))
            assert resp.json()["data"]["status"] == "UNDER REVIEW"
            
            resp = client.get(reverse("license-basic-info", args=[2]))
            assert resp.json()["data"]["status"] == "REJECTED"
            
            resp = client.get(reverse("license-basic-info", args=[3]))
            assert resp.json()["data"]["status"] == "SUBMITTED"
    
    def test_different_license_states(self, client, complete_license_payload, blockchain_state):
        """Test licenses in different states simultaneously"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create 4 licenses
            for i in range(4):
                payload = complete_license_payload.copy()
                payload["applicantName"] = f"Applicant {i+1}"
                payload["firmName"] = f"Firm {i+1}"
                client.post(
                    reverse("submit-license-application"),
                    data=json.dumps(payload),
                    content_type='application/json'
                )
            
            # Move licenses to different states
            states = ["SUBMITTED", "UNDER REVIEW", "DOCUMENTS VERIFIED", "APPROVED"]
            
            for i, state in enumerate(states, start=1):
                if state != "SUBMITTED":
                    # Progress through necessary states
                    if state in ["UNDER REVIEW", "DOCUMENTS VERIFIED", "APPROVED"]:
                        client.post(
                            reverse("update-license-status"),
                            data=json.dumps({
                                "licenseId": i,
                                "status": "UNDER_REVIEW",
                                "officerName": "Officer",
                                "role": "AGRICULTURE_OFFICER",
                                "remarks": "Review"
                            }),
                            content_type='application/json'
                        )
                    
                    if state in ["DOCUMENTS VERIFIED", "APPROVED"]:
                        client.post(
                            reverse("update-license-status"),
                            data=json.dumps({
                                "licenseId": i,
                                "status": "DOCUMENTS_VERIFIED",
                                "officerName": "Officer",
                                "role": "DEPUTY_DIRECTOR",
                                "remarks": "Verified"
                            }),
                            content_type='application/json'
                        )
                    
                    if state == "APPROVED":
                        for status_val in ["INSPECTION SCHEDULED", "INSPECTION COMPLETED"]:
                            client.post(
                                reverse("update-license-status"),
                                data=json.dumps({
                                    "licenseId": i,
                                    "status": status_val,
                                    "officerName": "Officer",
                                    "role": "AGRICULTURE_OFFICER",
                                    "remarks": "Processing"
                                }),
                                content_type='application/json'
                            )
                        
                        client.post(
                            reverse("update-license-status"),
                            data=json.dumps({
                                "licenseId": i,
                                "status": "APPROVED",
                                "officerName": "Director",
                                "role": "JOINT_DIRECTOR",
                                "remarks": "Approved",
                                "renewalPeriodDays": 365
                            }),
                            content_type='application/json'
                        )
            
            # Verify all states
            for i, expected_state in enumerate(states, start=1):
                resp = client.get(reverse("license-basic-info", args=[i]))
                assert resp.status_code == 200
                assert resp.json()["data"]["status"] == expected_state