import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

class LicenseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Mock license data
        self.license_data = {
            "name": "Test Farmer",
            "aadhaar": "123456789012",
            "location": "Test Location", 
            "license_type": "SEED_PRODUCTION",
            "seed_variety": "Test Variety",
            "crop_type": "Test Crop",
            "quantity": "100",
            "quality_parameters": "Test Parameters",
            "source": "Test Source"
        }
        
        # Mock blockchain responses
        self.mock_receipt = MagicMock()
        self.mock_receipt.transactionHash.hex.return_value = "0xabc123"
        self.mock_receipt.blockNumber = 12345
        
        self.license_summary_mock = [
            123,  # license_id
            "0x123...",  # farmer_address
            "Test Farmer",  # farmer_name
            "Test Location",  # location
            0,  # license_type
            0,  # status
            1234567890,  # application_date
            0,  # approval_date
            0,  # expiry_date
            True,  # is_active
            ("Test Variety", "Test Crop", "100", "Test Parameters", "Test Source")
        ]
        
        # Patch authentication
        self.auth_patcher = patch(
            'seed_license.views.RajSSOAuthentication.authenticate',
            return_value=(MagicMock(), None)
        )
        self.auth_patcher.start()
        
    def tearDown(self):
        self.auth_patcher.stop()
    
    def _mock_handler(self):
        handler_patcher = patch('seed_license.views.SeedLicenseHandler')
        mock_handler = handler_patcher.start()
        self.addCleanup(handler_patcher.stop)
        return mock_handler.return_value
    
    def _parse_response(self, response):
        return json.loads(response.content.decode('utf-8'))
    
    def test_license_creation_success(self):
        mock_handler = self._mock_handler()
        mock_handler.apply_for_license.return_value = (123, self.mock_receipt)
        
        response = self.client.post(
            reverse('license-create'),
            data=self.license_data,
            format='json'
        )
        response_data = self._parse_response(response)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_data['data']['application_id'], 123)
        mock_handler.apply_for_license.assert_called_once()
    
    def test_license_creation_missing_fields(self):
        invalid_data = self.license_data.copy()
        del invalid_data['name']
        del invalid_data['aadhaar']
        
        response = self.client.post(
            reverse('license-create'),
            data=invalid_data,
            format='json'
        )
        response_data = self._parse_response(response)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing required fields", response_data['error'])
    
    def test_get_license_detail_success(self):
        mock_handler = self._mock_handler()
        mock_handler.get_license_summary.return_value = self.license_summary_mock
        
        response = self.client.get(
            reverse('license-detail', kwargs={'license_id': 123})
        )
        response_data = self._parse_response(response)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # summary returned as list
        self.assertEqual(response_data['data'][0], 123)
    
    def test_license_status_update_success(self):
        mock_handler = self._mock_handler()
        mock_handler.update_license_status.return_value = self.mock_receipt
        
        response = self.client.post(
            reverse('license-status-update', kwargs={'license_id': 123}),
            data={"status": 1, "remarks": "Test remarks"},
            format='json'
        )
        response_data = self._parse_response(response)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data['data']['id'], 123)
    
    def test_license_status_view_success(self):
        mock_handler = self._mock_handler()
        mock_handler.contract.functions.getLicenseSummary.return_value.call.return_value = self.license_summary_mock
        mock_handler.contract.functions.isLicenseValid.return_value.call.return_value = True
        
        response = self.client.get(
            reverse('license-status', kwargs={'license_id': 123})
        )
        response_data = self._parse_response(response)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data['data']['status'], "APPLIED")
    
    def test_license_history_success(self):
        mock_handler = self._mock_handler()
        mock_handler.get_license_history.return_value = [
            {"timestamp": 1234567890, "new_status": 1, "remarks": "Test"}
        ]
        
        response = self.client.get(
            reverse('license-history', kwargs={'license_id': 123})
        )
        response_data = self._parse_response(response)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_data['data']['history']), 1)
    
    def test_certificate_download_not_approved(self):
        mock_handler = self._mock_handler()
        mock_handler.get_license_summary.return_value = {"status": 3}  # Not approved
        
        response = self.client.get(
            reverse('license-certificate', kwargs={'license_id': 123})
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_license_list_success(self):
        with patch('seed_license.views.License.objects') as mock_manager:
            mock_queryset = MagicMock()
            # Ensure slicing and order_by return same mock
            mock_manager.all.return_value = mock_queryset
            mock_queryset.order_by.return_value = mock_queryset
            mock_queryset.count.return_value = 1
            # Support iteration
            mock_license = MagicMock()
            mock_license.license_id = "123"
            mock_queryset.__iter__.return_value = iter([mock_license])

            response = self.client.get(reverse('license-list'))
            response_data = self._parse_response(response)

            results = response_data["results"]

            self.assertIsInstance(results, dict)
            self.assertIn("total", results)
            self.assertIn("licenses", results)
            self.assertEqual(results["total"], 1)
            self.assertEqual(len(results["licenses"]), 0)

    def test_transaction_status_success(self):
        mock_handler = self._mock_handler()
        mock_handler.get_transaction_info.return_value = {
            "tx_hash": "0xabc123",
            "status": "CONFIRMED"
        }
        
        response = self.client.get(
            reverse('transaction-status', kwargs={'tx_hash': '0xabc123'})
        )
        response_data = self._parse_response(response)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data['data']['status'], "CONFIRMED")
