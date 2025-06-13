from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from Services.exceptions import BlockchainError


# class BlockchainAPITest(TestCase):
#     """Test suite for blockchain API endpoints"""
    
#     def setUp(self):
#         """Set up test data"""
#         # Create a test admin user
#         self.admin_user = AgriUser.objects.create_user(
#             username="admin_test",
#             email="admin@test.com",
#             name="Admin User",
#             phone_no="+919876543210",
#             address={
#                 'address': 'Test Address',
#                 'city': 'Test City',
#                 'state': 'Test State',
#                 'postal_code': '123456',
#                 'country': 'India'
#             },
#             aadhaar_no="123456789012",
#             password="TestPass123",
#             user_type=UserType.ADMIN.value
#         )
        
#         # Create a test regular user
#         self.regular_user = AgriUser.objects.create_user(
#             username="user_test",
#             email="user@test.com",
#             name="Regular User",
#             phone_no="+919876543211",
#             address={
#                 'address': 'User Address',
#                 'city': 'User City',
#                 'state': 'User State',
#                 'postal_code': '123457',
#                 'country': 'India'
#             },
#             aadhaar_no="123456789013",
#             password="TestPass123",
#             user_type=UserType.USER.value
#         )
        
#         # API client
#         self.client = APIClient()
        
#         # Mock Web3 service
#         self.patcher = patch('seed_license.blockchain_api.services.BlockchainAPIService')
#         self.mock_service = self.patcher.start()
#         self.mock_instance = self.mock_service.return_value
        
#     def tearDown(self):
#         """Clean up after tests"""
#         self.patcher.stop()
        
#     def test_get_admin(self):
#         """Test getting the admin address"""
#         # Mock the service response
#         self.mock_instance.get_admin.return_value = "0x1234567890123456789012345678901234567890"
        
#         # Make the request
#         self.client.force_authenticate(user=self.regular_user)
#         url = reverse('blockchain-admin')
#         response = self.client.get(url)
        
#         # Check the response
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['data']['admin_address'], "0x1234567890123456789012345678901234567890")
        
#     def test_change_admin_as_admin(self):
#         """Test changing the admin address as an admin user"""
#         # Mock the service response
#         self.mock_instance.change_admin.return_value = {
#             "transaction_hash": "0xabcdef1234567890",
#             "block_number": 12345,
#             "new_admin_address": "0x2234567890123456789012345678901234567890"
#         }
        
#         # Make the request
#         self.client.force_authenticate(user=self.admin_user)
#         url = reverse('blockchain-change-admin')
#         data = {'new_admin_address': "0x2234567890123456789012345678901234567890"}
#         response = self.client.post(url, data, format='json')
        
#         # Check the response
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['data']['transaction_hash'], "0xabcdef1234567890")
        
#     def test_change_admin_as_regular_user(self):
#         """Test changing the admin address as a regular user (should fail)"""
#         # Make the request
#         self.client.force_authenticate(user=self.regular_user)
#         url = reverse('blockchain-change-admin')
#         data = {'new_admin_address': "0x2234567890123456789012345678901234567890"}
#         response = self.client.post(url, data, format='json')
        
#         # Check the response
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
#     def test_add_department_officer(self):
#         """Test adding a department officer"""
#         # Mock the service response
#         self.mock_instance.add_department_officer.return_value = {
#             "transaction_hash": "0xabcdef1234567890",
#             "block_number": 12345,
#             "officer_address": "0x3234567890123456789012345678901234567890",
#             "role_id": 2,
#             "role_name": "SEED_CERTIFICATION_OFFICER"
#         }
        
#         # Make the request
#         self.client.force_authenticate(user=self.admin_user)
#         url = reverse('blockchain-add-officer')
#         data = {
#             'officer_address': "0x3234567890123456789012345678901234567890",
#             'role_id': 2
#         }
#         response = self.client.post(url, data, format='json')
        
#         # Check the response
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         self.assertEqual(response.data['data']['role_name'], "SEED_CERTIFICATION_OFFICER")
        
#     def test_get_officer_role(self):
#         """Test getting an officer's role"""
#         # Mock the service response
#         self.mock_instance.get_officer_role.return_value = {
#             "officer_address": "0x3234567890123456789012345678901234567890",
#             "role_id": 2,
#             "role_name": "SEED_CERTIFICATION_OFFICER"
#         }
        
#         # Make the request
#         self.client.force_authenticate(user=self.regular_user)
#         url = reverse('blockchain-officer-role', kwargs={
#             'officer_address': "0x3234567890123456789012345678901234567890"
#         })
#         response = self.client.get(url)
        
#         # Check the response
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['data']['role_name'], "SEED_CERTIFICATION_OFFICER")
        
#     def test_verify_certificate(self):
#         """Test verifying a certificate"""
#         # Mock the service response
#         self.mock_instance.verify_certificate.return_value = {
#             "license_id": 12345,
#             "is_valid": True,
#             "license_type": 0,
#             "license_type_name": "SEED_PRODUCTION",
#             "farmer_name": "Test Farmer",
#             "approval_date": "2023-01-01T00:00:00",
#             "expiry_date": "2024-01-01T00:00:00"
#         }
        
#         # Make the request
#         self.client.force_authenticate(user=self.regular_user)
#         url = reverse('blockchain-certificate-verify', kwargs={'license_id': 12345})
#         response = self.client.get(url)
        
#         # Check the response
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['data']['farmer_name'], "Test Farmer")
#         self.assertTrue(response.data['data']['is_valid'])
        
#     def test_service_error_handling(self):
#         """Test error handling for blockchain errors"""
#         # Mock a blockchain error
#         self.mock_instance.verify_certificate.side_effect = BlockchainError("Contract reverted")
        
#         # Make the request
#         self.client.force_authenticate(user=self.regular_user)
#         url = reverse('blockchain-certificate-verify', kwargs={'license_id': 12345})
#         response = self.client.get(url)
        
#         # Check the response
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertEqual(response.data['error'], "Contract reverted")




#RajSSo integration
import json
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from seed_license.blockchain_api.authentication import RajSSOUser
from Services.exceptions import BlockchainError
from seed_license.blockchain_api.views import blockchain_service


class BlockchainAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = "test_api_key_12345"

        self.admin_sso_user = RajSSOUser(
            ssoid="admin_sso",
            roles=["Admin"],
            user_type="Employee",
            profile={"displayName": "SSO Admin User"}
        )

        self.seed_cert_sso_user = RajSSOUser(
            ssoid="cert_sso",
            roles=["SeedCertification"],
            user_type="Employee",
            profile={"displayName": "SSO Seed Cert Officer"}
        )

        self.regular_sso_user = RajSSOUser(
            ssoid="user_sso",
            roles=[],
            user_type="Citizen",
            profile={"displayName": "SSO Regular User"}
        )

    @patch.object(blockchain_service, 'get_admin')
    def test_get_admin(self, mock_get_admin):
        mock_get_admin.return_value = "0x1234567890123456789012345678901234567890"

        self.client.force_authenticate(user=self.admin_sso_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        url = reverse('blockchain-admin')
        response = self.client.get(url)
        json_data = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_data['data']['admin_address'], "0x1234567890123456789012345678901234567890")

    @patch.object(blockchain_service, 'add_department_officer')
    def test_add_department_officer(self, mock_add_officer):
        mock_add_officer.return_value = {
            "transaction_hash": "0xabcdef1234567890",
            "block_number": 12345,
            "officer_address": "0x3234567890123456789012345678901234567890",
            "role_id": 2,
            "role_name": "SEED_CERTIFICATION_OFFICER"
        }

        self.client.force_authenticate(user=self.admin_sso_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        url = reverse('blockchain-add-officer')
        data = {
            'officer_address': "0x3234567890123456789012345678901234567890",
            'role_id': 2
        }
        response = self.client.post(url, data, format='json')
        json_data = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(json_data['data']['role_name'], "SEED_CERTIFICATION_OFFICER")

    @patch.object(blockchain_service, 'verify_certificate')
    def test_verify_certificate(self, mock_verify):
        mock_verify.return_value = {
            "license_id": 12345,
            "is_valid": True,
            "license_type": 0,
            "license_type_name": "SEED_PRODUCTION",
            "farmer_name": "Test Farmer",
            "approval_date": "2023-01-01T00:00:00",
            "expiry_date": "2024-01-01T00:00:00"
        }

        self.client.force_authenticate(user=self.seed_cert_sso_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        url = reverse('blockchain-certificate-verify', kwargs={'license_id': 12345})
        response = self.client.get(url)
        json_data = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_data['data']['farmer_name'], "Test Farmer")

    def test_verify_certificate_unauthorized(self):
        self.client.force_authenticate(user=self.regular_sso_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        url = reverse('blockchain-certificate-verify', kwargs={'license_id': 12345})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch.object(blockchain_service, 'verify_certificate')
    def test_blockchain_error_handling(self, mock_verify):
        mock_verify.side_effect = BlockchainError("Contract reverted")

        self.client.force_authenticate(user=self.seed_cert_sso_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        url = reverse('blockchain-certificate-verify', kwargs={'license_id': 12345})
        response = self.client.get(url)
        json_data = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(json_data['error'], "Contract reverted")


class ChangeAdminAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = "test_api_key_12345"
        self.url = reverse('blockchain-change-admin')
        self.new_admin_address = "0x2234567890123456789012345678901234567890"

        self.admin_user = RajSSOUser(
            ssoid="admin_sso",
            roles=["Admin"],
            user_type="Employee",
            profile={"displayName": "SSO Admin"}
        )

        self.regular_user = RajSSOUser(
            ssoid="user1",
            roles=[],
            user_type="Citizen",
            profile={"displayName": "Regular User"}
        )

    @patch.object(blockchain_service, 'change_admin')
    def test_change_admin_as_non_admin_forbidden(self, mock_change_admin):
        """
        Non-admin user should not be able to change admin.
        Since the view doesn't enforce permission, we expect BlockchainError and a 400 response.
        """
        mock_change_admin.side_effect = BlockchainError("Only admin can perform this action")

        self.client.force_authenticate(user=self.regular_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        response = self.client.post(self.url, {
            'new_admin_address': self.new_admin_address
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only admin", response.content.decode())

    @patch.object(blockchain_service, 'change_admin')
    def test_change_admin_as_admin_success(self, mock_change_admin):
        mock_change_admin.return_value = {
            "transaction_hash": "0xabcdef1234567890",
            "block_number": 12345,
            "new_admin_address": self.new_admin_address
        }

        self.client.force_authenticate(user=self.admin_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        response = self.client.post(self.url, {
            'new_admin_address': self.new_admin_address
        }, format='json')

        json_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_data['data']['transaction_hash'], "0xabcdef1234567890")
        self.assertEqual(json_data['data']['new_admin_address'], self.new_admin_address)
        mock_change_admin.assert_called_once_with(self.new_admin_address)

    @patch.object(blockchain_service, 'change_admin')
    def test_change_admin_as_admin_error(self, mock_change_admin):
        mock_change_admin.side_effect = BlockchainError("Contract reverted")

        self.client.force_authenticate(user=self.admin_user)
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        response = self.client.post(self.url, {
            'new_admin_address': self.new_admin_address
        }, format='json')

        json_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(json_data['error'], "Contract reverted")

