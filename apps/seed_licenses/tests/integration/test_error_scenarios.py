"""
Integration tests for various error scenarios across the system
"""
import pytest
from unittest.mock import patch
from django.urls import reverse
from apps.seed_licenses.tests.integration.fixtures import blockchain_state, complete_license_payload
from apps.seed_licenses.tests.conftest import client


@pytest.mark.django_db
class TestErrorScenarios:
    """Test various error scenarios across the system"""
    
    def test_invalid_status_transitions(self, client, complete_license_payload, blockchain_state):
        """Test that invalid status transitions are rejected"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            client.post(
                reverse("submit-license-application"),
                data=complete_license_payload,
                content_type='application/json'
            )
            license_id = 1
            
            # Try to skip directly to APPROVED (invalid transition from SUBMITTED)
            resp = client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": license_id,
                    "status": "APPROVED",
                    "officerName": "Officer",
                    "role": "JOINT_DIRECTOR",
                    "remarks": "Trying invalid transition",
                    "renewalPeriodDays": 365
                },
                content_type='application/json'
            )
            assert resp.status_code == 400
            assert "Invalid status transition" in resp.json()["error"]
    
    def test_nonexistent_license_operations(self, client, blockchain_state):
        """Test operations on non-existent licenses"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Try to get info for non-existent license
            resp = client.get(reverse("license-basic-info", args=[999]))
            assert resp.status_code == 500
            assert "does not exist" in resp.json()["error"]
            
            # Try to get history for non-existent license
            resp = client.get(reverse("license-action-history", args=[999]))
            assert resp.status_code == 500
    
    def test_missing_required_fields(self, client, blockchain_state):
        """Test submission with missing required fields"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Try to submit with missing applicant name
            incomplete_payload = {
                "firmName": "Test Firm",
                "cropVariety": "Wheat",
                "state": "Rajasthan"
            }
            
            resp = client.post(
                reverse("submit-license-application"),
                data=incomplete_payload,
                content_type='application/json'
            )
            assert resp.status_code in [400, 500]
    
    def test_invalid_status_value(self, client, complete_license_payload, blockchain_state):
        """Test updating to an invalid status value"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            client.post(
                reverse("submit-license-application"),
                data=complete_license_payload,
                content_type='application/json'
            )
            license_id = 1
            
            # Try to update to invalid status
            resp = client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": license_id,
                    "status": "INVALID_STATUS",
                    "officerName": "Officer",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Test"
                },
                content_type='application/json'
            )
            assert resp.status_code in [400, 500]
    
    def test_update_without_required_role(self, client, complete_license_payload, blockchain_state):
        """Test status update without proper role"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            client.post(
                reverse("submit-license-application"),
                data=complete_license_payload,
                content_type='application/json'
            )
            license_id = 1
            
            # Try to update status without role
            resp = client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": license_id,
                    "status": "UNDER_REVIEW",
                    "officerName": "Officer",
                    "remarks": "Test"
                },
                content_type='application/json'
            )
            assert resp.status_code in [400, 500]
    
    def test_rejection_without_remarks(self, client, complete_license_payload, blockchain_state):
        """Test that rejection requires remarks"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create and move to review
            client.post(
                reverse("submit-license-application"),
                data=complete_license_payload,
                content_type='application/json'
            )
            license_id = 1
            
            client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": license_id,
                    "status": "UNDER_REVIEW",
                    "officerName": "Officer",
                    "role": "AGRICULTURE_OFFICER",
                    "remarks": "Review"
                },
                content_type='application/json'
            )
            
            # Try to reject without remarks
            resp = client.post(
                reverse("update-license-status"),
                data={
                    "licenseId": license_id,
                    "status": "REJECTED",
                    "officerName": "Officer",
                    "role": "JOINT_DIRECTOR",
                    "remarks": ""
                },
                content_type='application/json'
            )
            # System should reject or require remarks
            assert resp.status_code in [400, 500] or (
                resp.status_code == 202 and 
                "remarks" in resp.json().get("error", "").lower()
            )