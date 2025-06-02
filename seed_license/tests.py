from rest_framework.test import APITestCase, APIClient
from django.urls import reverse
from django.utils.timezone import now
from unittest.mock import patch, MagicMock
from django.test.utils import override_settings
from seed_license.models import License, BlockchainTransaction, OfficerAction
from django.contrib.auth import get_user_model
import json
from rest_framework import status
User = get_user_model()

@override_settings(API_KEYS={"test-api-key": "officer123"})
class SeedLicenseAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="farmer1", password="test1234")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)  # Authenticate the user for all requests
        self.valid_license_data = {
            "name": "Test Farmer",
            "aadhaar": "123456789012",
            "location": "Village X",
            "license_type": "SEED_PRODUCTION",
            "seed_variety": "Variety A",
            "crop_type": "Wheat",
            "quantity": 100,
            "quality_parameters": "High quality",
            "source": "Govt Seed Center"
        }
        self.api_key = "test-api-key"
        self.headers = {"HTTP_X_API_KEY": self.api_key}

    def test_license_application_missing_fields(self):
        response = self.client.post(reverse("license-create"), {}, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_license_list_empty(self):
        response = self.client.get(reverse("license-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['count'], 0)

    def test_transaction_history_empty(self):
        response = self.client.get(reverse("transaction-history"), **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['count'], 0)

    def test_record_officer_action_missing_fields(self):
        officer_user = User.objects.create_user(
        username="officer1",
        password="test1234",
        )
        self.client.force_authenticate(user=officer_user)
        
        response = self.client.post(reverse("record-officer-action"), 
                                {}, 
                                content_type="application/json", 
                                **self.headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_officer_actions_empty(self):
        response = self.client.get(reverse("officer-actions", kwargs={"officer_id": "officer123"}), 
                                 **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['data']['actions']), 0)

    @patch("seed_license.seed_license_handler.SeedLicenseHandler.get_license_status", return_value="APPLIED")
    @patch("seed_license.seed_license_handler.SeedLicenseHandler.is_license_valid", return_value=True)
    def test_get_license_status_not_found(self, mock_valid, mock_status):
        response = self.client.get(reverse("license-status", kwargs={"license_id": 9999}))
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        if response.status_code == 200:
            self.assertEqual(response.json()['data']['status'], "APPLIED")

    @patch("seed_license.seed_license_handler.SeedLicenseHandler.get_license_history", return_value=[])
    def test_get_license_history_not_found(self, mock_hist):
        response = self.client.get(reverse("license-history", kwargs={"license_id": 9999}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['data']['history'], [])

    def test_license_certificate_not_found(self):
        response = self.client.get(reverse("license-certificate", kwargs={"license_id": 9999}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_license_certificate_not_approved(self):
        lic = License.objects.create(
            applicant=self.user,
            license_id=1,
            license_type="SEED_PRODUCTION",
            crop_type="Wheat",
            seed_variety="Variety A",
            quantity=100,
            location="X",
            quality_parameters="Q",
            source="S",
            aadhaar="123456789012",
            blockchain_tx_id="0x123",
            status="APPLIED",
        )
        response = self.client.get(reverse("license-certificate", kwargs={"license_id": lic.license_id}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("seed_license.seed_license_handler.SeedLicenseHandler.get_license_summary", 
          return_value=[1, "0xabc", "Test Farmer", "Village X", "SEED_PRODUCTION", "APPLIED", 
                       now().timestamp(), None, None, True, ["Variety A", "Wheat", 100, "HQ", "Gov"]])
    def test_get_license_detail_success(self, mock_summary):
        response = self.client.get(reverse("license-detail", kwargs={"license_id": 1}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['data']['license_id'], 1)

    @patch("seed_license.seed_license_handler.SeedLicenseHandler.apply_for_license")
    @patch("seed_license.views.w3.eth.get_block")
    def test_license_application_success(self, mock_get_block, mock_apply):
        mock_apply.return_value = (1, MagicMock(transactionHash=MagicMock(hex=lambda: "0xabc"), blockNumber=100))
        mock_get_block.return_value = MagicMock(timestamp=now().timestamp())

        response = self.client.post(reverse("license-create"), 
                                  json.dumps(self.valid_license_data), 
                                  content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['data']['license_id'], 1)
        self.assertEqual(response.json()['data']['status'], "APPLIED")

    # @patch("seed_license.seed_license_handler.SeedLicenseHandler.update_license_status")
    # @patch("seed_license.views.w3.eth.get_block")
    # def test_license_status_update_success(self, mock_get_block, mock_update):
    #     lic = License.objects.create(
    #         applicant=self.user,
    #         license_id=123,
    #         license_type="SEED_PRODUCTION",
    #         crop_type="Wheat",
    #         seed_variety="Variety A",
    #         quantity=100,
    #         location="X",
    #         quality_parameters="Q",
    #         source="S",
    #         aadhaar="123456789012",
    #         blockchain_tx_id="0x123",
    #         status="APPLIED",
    #     )
    #     mock_update.return_value = MagicMock(transactionHash=MagicMock(hex=lambda: "0xtx"), blockNumber=50)
    #     mock_get_block.return_value = MagicMock(timestamp=now().timestamp())

    #     response = self.client.post(reverse("license-status-update"), 
    #                               json.dumps({
    #                                   "license_id": lic.license_id,
    #                                   "status": 1,
    #                                   "remarks": "Documents verified",
    #                               }), 
    #                               content_type="application/json",
    #                               **self.headers)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(response.json()['data']['status'], 1)
    #     self.assertEqual(response.json()['data']['license_id'], lic.license_id)

def test_record_officer_action_success(self):
    # Create an officer user
    officer_user = User.objects.create_user(
        username="officer1",
        password="test1234",
        is_agriculture_officer=True
    )
    self.client.force_authenticate(user=officer_user)
    
    lic = License.objects.create(
        applicant=self.user,
        license_id=99,
        license_type="SEED_PRODUCTION",
        crop_type="Wheat",
        seed_variety="Variety A",
        quantity=100,
        location="X",
        quality_parameters="Q",
        source="S",
        aadhaar="123456789012",
        blockchain_tx_id="0x123",
        status="APPLIED",
    )
    OfficerAction.objects.all().delete()
    
    with patch("seed_license.views.APIKeyAuthentication.authenticate", return_value=(None, "officer123")):
        response = self.client.post(reverse("record-officer-action"), 
                                  json.dumps({
                                      "license_id": lic.license_id,
                                      "action_type": "DOC_VERIFICATION",
                                      "remarks": "All good",
                                      "tx_hash": "0xabc123"
                                  }), 
                                  content_type="application/json", 
                                  **self.headers)
    self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    self.assertEqual(OfficerAction.objects.count(), 1)
    self.assertEqual(OfficerAction.objects.first().officer_id, "officer123")