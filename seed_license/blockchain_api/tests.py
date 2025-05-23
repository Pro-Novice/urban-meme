from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

User = get_user_model()

class BlockchainAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass',
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='userpass'
        )

    @patch('seed_license.blockchain_api.views.blockchain_service')
    def test_get_admin(self, mock_service):
        mock_service.get_admin.return_value = "0x1234567890123456789012345678901234567890"
        response = self.client.get('/api/blockchain/contract/admin/')
        self.assertEqual(response.data['admin_address'], "0x1234567890123456789012345678901234567890")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('seed_license.blockchain_api.views.blockchain_service')
    def test_change_admin_as_admin(self, mock_service):
        self.client.force_authenticate(user=self.admin_user)
        mock_service.change_admin.return_value = True
        response = self.client.post(
            '/api/blockchain/contract/admin/change/',
            {'new_admin_address': '0xnewadminaddress'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)

    @patch('seed_license.blockchain_api.views.blockchain_service')
    def test_change_admin_as_regular_user(self, mock_service):
        self.client.force_authenticate(user=self.regular_user)
        mock_service.change_admin.side_effect = Exception("Permission denied")
        response = self.client.post(
            '/api/blockchain/contract/admin/change/',
            {'new_admin_address': '0xnewadminaddress'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('seed_license.blockchain_api.views.blockchain_service')
    def test_add_department_officer(self, mock_service):
        self.client.force_authenticate(user=self.admin_user)
        mock_service.add_department_officer.return_value = True
        response = self.client.post(
            '/api/blockchain/contract/officers/add/',
            {'officer_address': '0xofficer', 'role_id': 1},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data)

    @patch('seed_license.blockchain_api.views.blockchain_service')
    def test_get_officer_role(self, mock_service):
        mock_service.get_officer_role.return_value = {"role_name": "SEED_CERTIFICATION_OFFICER"}
        response = self.client.get('/api/blockchain/contract/officers/role/0xofficer/')
        self.assertEqual(response.data['role_name'], "SEED_CERTIFICATION_OFFICER")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('seed_license.blockchain_api.views.blockchain_service')
    def test_verify_certificate(self, mock_service):
        mock_service.verify_certificate.return_value = {
            'farmer_name': 'Test Farmer',
            'valid': True
        }
        response = self.client.get('/api/blockchain/contract/certificates/verify/123/')
        self.assertEqual(response.data['farmer_name'], "Test Farmer")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('seed_license.blockchain_api.views.blockchain_service')
    def test_service_error_handling(self, mock_service):
        mock_service.get_admin.side_effect = Exception("Blockchain error")
        response = self.client.get('/api/blockchain/contract/admin/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)