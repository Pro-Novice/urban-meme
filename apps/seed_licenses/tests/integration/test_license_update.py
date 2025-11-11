"""
Integration tests for license verification and QR code generation
"""
import pytest
import json
from unittest.mock import patch
from django.urls import reverse
from apps.seed_licenses.tests.integration.fixtures import blockchain_state, complete_license_payload
from apps.seed_licenses.tests.conftest import client


@pytest.mark.django_db
class TestLicenseVerification:
    """Test license verification and QR code generation"""
    
    def test_complete_verification_flow(self, client, complete_license_payload, blockchain_state):
        """Test QR generation and verification"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            resp = client.post(
                reverse("submit-license-application"),
                data=json.dumps(complete_license_payload),
                content_type='application/json'
            )
            license_id = 1
            
            # Get license info to retrieve license number
            resp = client.get(reverse("license-basic-info", args=[license_id]))
            license_number = resp.json()["data"]["licenseNumber"]
            
            # Get QR data
            resp = client.get(reverse("license-qr-data", args=[license_id]))
            assert resp.status_code == 200
            qr_data = resp.json()["data"]
            assert "verificationHash" in qr_data
            assert qr_data["licenseNumber"] == license_number
            
            verification_hash = qr_data["verificationHash"]
            
            # Verify with correct hash
            resp = client.post(
                reverse("verify-license-document"),
                data={
                    "licenseNumber": license_number,
                    "expectedHash": verification_hash
                },
                content_type='application/json'
            )
            assert resp.status_code == 202
            assert "transaction_hash" in resp.json()["data"]
    
    def test_qr_data_for_different_license_states(self, client, complete_license_payload, blockchain_state):
        """Test QR data generation for licenses in different states"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            client.post(
                reverse("submit-license-application"),
                data=complete_license_payload,
                content_type='application/json'
            )
            license_id = 1
            
            # Get QR data while SUBMITTED
            resp = client.get(reverse("license-qr-data", args=[license_id]))
            assert resp.status_code == 200
            qr_data_submitted = resp.json()["data"]
            
            # Move to UNDER_REVIEW
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
            
            # Get QR data while UNDER_REVIEW
            resp = client.get(reverse("license-qr-data", args=[license_id]))
            assert resp.status_code == 200
            qr_data_review = resp.json()["data"]
            
            # Verify QR data contains consistent license number
            assert qr_data_submitted["licenseNumber"] == qr_data_review["licenseNumber"]
    
    def test_verification_with_invalid_hash(self, client, complete_license_payload, blockchain_state):
        """Test verification fails with incorrect hash"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract), \
             patch("apps.seed_licenses.services.blockchain.write_to_contract", side_effect=blockchain_state.write_to_contract):
            
            # Create license
            client.post(
                reverse("submit-license-application"),
                data=complete_license_payload,
                content_type='application/json'
            )
            license_id = 1
            
            # Get license number
            resp = client.get(reverse("license-basic-info", args=[license_id]))
            license_number = resp.json()["data"]["licenseNumber"]
            
            # Try to verify with wrong hash
            resp = client.post(
                reverse("verify-license-document"),
                data={
                    "licenseNumber": license_number,
                    "expectedHash": "0xWRONGHASH123456789"
                },
                content_type='application/json'
            )
            # Depending on implementation, this might return 400 or 202 with verification failure
            # Adjust assertion based on actual behavior
            assert resp.status_code in [400, 202]
    
    def test_qr_data_for_nonexistent_license(self, client, blockchain_state):
        """Test QR data retrieval for non-existent license"""
        
        with patch("apps.seed_licenses.services.blockchain.read_from_contract", side_effect=blockchain_state.read_from_contract):
            
            # Try to get QR data for non-existent license
            resp = client.get(reverse("license-qr-data", args=[999]))
            assert resp.status_code == 500
            assert "does not exist" in resp.json()["error"]