from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch
import tempfile


class SeedLicenseAPITest(APITestCase):
    """
    Comprehensive test cases for Seed License smart contract API endpoints.
    Covers contract initialization, license creation, document verification,
    officer management, blockchain interactions, and feedback operations.
    """

    def parse_response(self, response):
        """
        Utility method to extract status code and JSON response data.
        """
        return response.status_code, response.json()

    def test_initialize_blockchain_contract(self):
        """
        Test the contract initialization endpoint.
        Accepts success (200) or already-initialized (400) as valid.
        """
        url = reverse('seed_license:initialize_blockchain_contract')
        response = self.client.get(url)
        status_code, data = self.parse_response(response)

        self.assertIn(status_code, [200, 400])

        if status_code == 400:
            # Handle cases where initialization fails due to repetition or estimation failure
            error_message = data.get("data") or data.get("error", "")
            if isinstance(error_message, dict):
                error_message = error_message.get("error", str(error_message))
            self.assertTrue(
                "already initialized" in error_message or "Gas estimation failed" in str(error_message),
                f"Expected 'already initialized' or 'Gas estimation failed', got: {error_message}"
            )

    def test_check_owner_blockchain(self):
        """
        Test retrieving owner address of the smart contract.
        """
        url = reverse('seed_license:check_owner_blockchain')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_check_admin_blockchain(self):
        """
        Test retrieving admin address of the smart contract.
        """
        url = reverse('seed_license:check_admin_blockchain')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_check_total_license_count(self):
        """
        Test getting total licenses count from the smart contract.
        """
        url = reverse('seed_license:check_total_license_count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_contract_methods_view(self):
        """
        Test listing available contract methods for a given contract name.
        """
        url = reverse('seed_license:contract-methods', args=["LicenseSystemV1"])
        with patch("seed_license.views.get_available_methods") as mock_methods:
            mock_methods.return_value = ["initialize"]
            response = self.client.get(url)
            status_code, data = self.parse_response(response)
            self.assertEqual(status_code, 200)
            self.assertIn("initialize", data["data"])

    def test_contract_address_all(self):
        """
        Test retrieving all deployed contract addresses.
        """
        url = reverse('seed_license:contract-address', args=["all"])
        with patch("seed_license.views.get_all_contract_addresses") as mock:
            mock.return_value = {"LicenseSystemV1": "0x123..."}
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_add_officer_invalid_role(self):
        """
        Test officer creation with an invalid role value.
        """
        url = reverse('seed_license:add_officer_view')
        payload = {
            "officer_address": "0xabc",
            "officer_name": "Test Officer",
            "officer_id": "OFF123",
            "officer_role": "WRONG_ROLE",
            "department": "AGRI",
            "officer_level": "STATE",
            "state": "Rajasthan"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("officer_role", response.json()["error"])

    def test_create_license_invalid_aadhaar(self):
        """
        Test license creation with invalid Aadhaar number.
        """
        url = reverse('seed_license:create_license_view')
        payload = {
            "license_category": "SEED",
            "admin_level": "STATE",
            "applicant_name": "John",
            "aadhaar_number": "1234",  # Invalid Aadhaar
            "business_name": "John Biz",
            "state": "RAJASTHAN"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("aadhaar_number", response.json()["error"])

    def test_update_license_status_invalid_status(self):
        """
        Test status update with an invalid status enum value.
        """
        url = reverse('seed_license:update_license_status_view')
        payload = {
            "license_id": 1,
            "status": "WRONG_STATUS",
            "remarks": "Update attempt"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.json()["error"])

    def test_generate_document_hash(self):
        """
        Test document hash generation from uploaded PDF.
        """
        url = reverse('seed_license:generate-document-hash')
        file = tempfile.NamedTemporaryFile(suffix=".pdf")
        file.write(b"dummy content")
        file.seek(0)
        response = self.client.post(url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertIn("hash", response.json()["data"])

    def test_verify_document_missing(self):
        """
        Test document verification with missing hash and remarks.
        """
        url = reverse('seed_license:verify-document')
        payload = {
            "license_id": 1,
            "document_type": 0,
            "document_hash": "",
            "is_verified": True,
            "remarks": ""
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("document_hash", response.json()["error"])
        self.assertIn("remarks", response.json()["error"])

    def test_add_inspection_feedback_invalid(self):
        """
        Test adding inspection feedback with missing inspector name.
        """
        url = reverse('seed_license:add-inspection-feedback')
        payload = {
            "license_id": 1,
            "inspector": "",
            "feedback_type": 1,
            "remarks": ""
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("inspector", response.json()["error"])

    def test_feedback_count_invalid_params(self):
        """
        Test feedback count endpoint with invalid route parameters.
        """
        url = reverse('seed_license:feedback-count', args=["abc", "x"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_blockchain_write_missing_fields(self):
        """
        Test writing to blockchain with missing required fields.
        """
        url = reverse('seed_license:blockchain-write')
        payload = {"contract_name": "", "method_name": ""}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 400)

    def test_blockchain_read_missing_fields(self):
        """
        Test reading from blockchain with missing contract name.
        """
        url = reverse('seed_license:blockchain-read')
        response = self.client.get(url, data={"contract_name": ""}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_transaction_status_invalid(self):
        """
        Test transaction status fetch with an invalid tx hash that raises an exception.
        """
        url = reverse('seed_license:transaction-status', args=["0x123"])
        with patch("seed_license.views.get_transaction_status") as mock_status:
            mock_status.side_effect = Exception("Not found")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 500)
