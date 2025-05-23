"""
Unit and Integration tests for RajOfficer views
"""
import json
import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from Raj_Officer.models import RajOfficer
from agri_backend.enums import Gender, Status, UserType

User = get_user_model()


class RajOfficerViewsTestCase(APITestCase):
    """Test cases for RajOfficer views"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create test admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass',
            is_superuser=True
        )

        # Create test regular user
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass'
        )

        self.valid_officer_data = {
            'user_id': 'RAJKSNOFSR12345',
            'name': 'Test Officer',
            'user_name': 'testofficer',
            'mobile_number': '9876543210',
            'email': 'test@example.com',
            'address': 'Test Address',
            'gender': Gender.MALE.value,
            'aadhar_number': '123456789012',
            'designation': 'AGRICULTURE_OFFICER',
            'department': 'AGRICULTURE',
            'role': 'FIELD_OFFICER',
            'password': 'testpassword123',
            'confirm_password': 'testpassword123'
        }

        # Mock blockchain address for tests
        self.mock_blockchain_address = '0x1234567890123456789012345678901234567890'

    def authenticate_admin(self):
        """Helper method to authenticate as admin"""
        self.client.force_authenticate(user=self.admin_user)

    def authenticate_regular(self):
        """Helper method to authenticate as regular user"""
        self.client.force_authenticate(user=self.regular_user)


class TestRegisterRajKisanOfficer(RajOfficerViewsTestCase):
    """Test cases for register_raj_kisan_officer view"""

    @patch('Raj_Officer.views.BlockchainAPIService')
    @patch('Raj_Officer.views.logger')
    def test_register_officer_success(self, mock_logger, mock_blockchain_service):
        """Test successful officer registration"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.add_department_officer.return_value = {
            'transaction_hash': '0xabcdef123456'
        }
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        # Add blockchain address to test data
        data = self.valid_officer_data.copy()
        data['blockchain_address'] = self.mock_blockchain_address

        response = self.client.post('/admin/register-officer', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(RajOfficer.objects.filter(user_id='RAJKSNOFSR12345').exists())

        # Verify blockchain service was called
        mock_service.add_department_officer.assert_called_once()

    def test_register_officer_invalid_data(self):
        """Test officer registration with invalid data"""
        self.authenticate_admin()

        invalid_data = self.valid_officer_data.copy()
        invalid_data['mobile_number'] = '1234567890'  # Invalid format

        response = self.client.post('/admin/register-officer', invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('mobile_number', response.data['err'])

    def test_register_officer_unauthorized(self):
        """Test officer registration without admin privileges"""
        self.authenticate_regular()

        response = self.client.post('/admin/register-officer', self.valid_officer_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only admin users can register officers', response.data['err'])

    def test_register_officer_unauthenticated(self):
        """Test officer registration without authentication"""
        response = self.client.post('/admin/register-officer', self.valid_officer_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_register_officer_blockchain_failure(self, mock_blockchain_service):
        """Test officer registration with blockchain failure"""
        # Mock blockchain service to raise exception
        mock_service = Mock()
        mock_service.add_department_officer.side_effect = Exception("Blockchain error")
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        data = self.valid_officer_data.copy()
        data['blockchain_address'] = self.mock_blockchain_address

        response = self.client.post('/admin/register-officer', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Verify rollback - officer should not exist in database
        self.assertFalse(RajOfficer.objects.filter(user_id='RAJKSNOFSR12345').exists())

    def test_register_officer_missing_required_fields(self):
        """Test officer registration with missing required fields"""
        self.authenticate_admin()

        incomplete_data = {
            'name': 'Test Officer',
            'mobile_number': '9876543210',
            # Missing user_id, password, confirm_password, etc.
        }

        response = self.client.post('/admin/register-officer', incomplete_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('user_id', response.data['err'])


class TestListAllRajKisanOfficers(RajOfficerViewsTestCase):
    """Test cases for list_all_raj_kisan_officers view"""

    def setUp(self):
        super().setUp()
        # Create test officers
        self.officer1 = RajOfficer.objects.create(
            user_id='RAJKSNOFSR11111',
            name='Officer 1',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE',
            blockchain_address='0x1111111111111111111111111111111111111111'
        )
        self.officer2 = RajOfficer.objects.create(
            user_id='RAJKSNOFSR22222',
            name='Officer 2',
            designation='DISTRICT_COLLECTOR',
            department='REVENUE'
        )

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_list_officers_success(self, mock_blockchain_service):
        """Test successful officer listing"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.is_authorized_officer.return_value = {'is_authorized': True}
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        response = self.client.get('/admin/officers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)

        # Check blockchain verification was called for officer with address
        mock_service.is_authorized_officer.assert_called()

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_list_officers_blockchain_verification_failure(self, mock_blockchain_service):
        """Test officer listing with blockchain verification failure"""
        # Mock blockchain service to raise exception
        mock_service = Mock()
        mock_service.is_authorized_officer.side_effect = Exception("Blockchain error")
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        response = self.client.get('/admin/officers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still return officers but with blockchain_verified = False
        officer_data = response.data['data'][0]
        self.assertFalse(officer_data['blockchain_verified'])

    def test_list_officers_unauthenticated(self):
        """Test officer listing without authentication"""
        response = self.client.get('/admin/officers/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestGetRajKisanOfficerDetail(RajOfficerViewsTestCase):
    """Test cases for get_raj_kisan_officer_detail view"""

    def setUp(self):
        super().setUp()
        self.officer = RajOfficer.objects.create(
            user_id='RAJKSNOFSR12345',
            name='Test Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE',
            blockchain_address='0x1234567890123456789012345678901234567890'
        )

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_get_officer_detail_success(self, mock_blockchain_service):
        """Test successful officer detail retrieval"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.is_authorized_officer.return_value = {'is_authorized': True}
        mock_service.get_officer_role.return_value = {'role_name': 'AGRICULTURE_OFFICER'}
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        response = self.client.get(f'/admin/officers?officer_id={self.officer.user_id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['name'], 'Test Officer')
        self.assertTrue(response.data['data']['blockchain_verified'])
        self.assertEqual(response.data['data']['blockchain_role'], 'AGRICULTURE_OFFICER')

    def test_get_officer_detail_not_found(self):
        """Test officer detail retrieval for non-existent officer"""
        self.authenticate_admin()

        response = self.client.get('/admin/officers?officer_id=NONEXISTENT')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Officer not found', response.data['err'])

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_get_officer_detail_no_blockchain_address(self, mock_blockchain_service):
        """Test officer detail retrieval for officer without blockchain address"""
        # Create officer without blockchain address
        officer_no_blockchain = RajOfficer.objects.create(
            user_id='RAJKSNOFSR99999',
            name='No Blockchain Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE'
        )

        self.authenticate_admin()

        response = self.client.get(f'/admin/officers?officer_id={officer_no_blockchain.user_id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not call blockchain service for verification
        mock_blockchain_service.assert_not_called()


class TestUpdateRajKisanOfficer(RajOfficerViewsTestCase):
    """Test cases for update_raj_kisan_officer view"""

    def setUp(self):
        super().setUp()
        self.officer = RajOfficer.objects.create(
            user_id='RAJKSNOFSR12345',
            name='Test Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE',
            blockchain_address='0x1234567890123456789012345678901234567890'
        )

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_update_officer_success(self, mock_blockchain_service):
        """Test successful officer update"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.remove_department_officer.return_value = True
        mock_service.add_department_officer.return_value = {
            'transaction_hash': '0xabcdef123456'
        }
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        update_data = {
            'name': 'Updated Officer Name',
            'blockchain_address': '0x9999999999999999999999999999999999999999',
            'role': 'SENIOR_OFFICER'
        }

        response = self.client.put(
            f'/admin/officers/update?officer_id={self.officer.user_id}',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify officer was updated
        updated_officer = RajOfficer.objects.get(user_id=self.officer.user_id)
        self.assertEqual(updated_officer.name, 'Updated Officer Name')

        # Verify blockchain operations were called
        mock_service.remove_department_officer.assert_called_once()
        mock_service.add_department_officer.assert_called_once()

    def test_update_officer_not_found(self):
        """Test officer update for non-existent officer"""
        self.authenticate_admin()

        update_data = {'name': 'Updated Name'}

        response = self.client.put(
            '/admin/officers/update?officer_id=NONEXISTENT',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Officer not found', response.data['err'])

    def test_update_officer_unauthorized(self):
        """Test officer update without admin privileges"""
        self.authenticate_regular()

        update_data = {'name': 'Updated Name'}

        response = self.client.put(
            f'/admin/officers/update?officer_id={self.officer.user_id}',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only admin users can update officers', response.data['err'])

    def test_update_officer_invalid_data(self):
        """Test officer update with invalid data"""
        self.authenticate_admin()

        invalid_data = {
            'mobile_number': '1234567890',  # Invalid format
        }

        response = self.client.put(
            f'/admin/officers/update?officer_id={self.officer.user_id}',
            invalid_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDeleteRajKisanOfficer(RajOfficerViewsTestCase):
    """Test cases for delete_raj_kisan_officer view"""

    def setUp(self):
        super().setUp()
        self.officer = RajOfficer.objects.create(
            user_id='RAJKSNOFSR12345',
            name='Test Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE',
            blockchain_address='0x1234567890123456789012345678901234567890'
        )

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_delete_officer_success(self, mock_blockchain_service):
        """Test successful officer deletion"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.remove_department_officer.return_value = {
            'transaction_hash': '0xabcdef123456'
        }
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        response = self.client.delete(f'/admin/officers/delete?officer_id={self.officer.user_id}')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify officer was deleted from database
        self.assertFalse(RajOfficer.objects.filter(user_id=self.officer.user_id).exists())

        # Verify blockchain operation was called
        mock_service.remove_department_officer.assert_called_once_with(
            self.officer.blockchain_address
        )

    def test_delete_officer_not_found(self):
        """Test officer deletion for non-existent officer"""
        self.authenticate_admin()

        response = self.client.delete('/admin/officers/delete?officer_id=NONEXISTENT')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Officer not found', response.data['err'])

    def test_delete_officer_unauthorized(self):
        """Test officer deletion without admin privileges"""
        self.authenticate_regular()

        response = self.client.delete(f'/admin/officers/delete?officer_id={self.officer.user_id}')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only admin users can delete officers', response.data['err'])

    def test_delete_officer_no_blockchain_address(self):
        """Test deletion of officer without blockchain address"""
        # Create officer without blockchain address
        officer_no_blockchain = RajOfficer.objects.create(
            user_id='RAJKSNOFSR99999',
            name='No Blockchain Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE'
        )

        self.authenticate_admin()

        response = self.client.delete(f'/admin/officers/delete?officer_id={officer_no_blockchain.user_id}')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify officer was deleted
        self.assertFalse(RajOfficer.objects.filter(user_id=officer_no_blockchain.user_id).exists())


@pytest.mark.django_db
class TestRajOfficerViewsPytest:
    """Pytest version of view tests"""

    @pytest.fixture
    def api_client(self):
        """API client fixture"""
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        """Admin user fixture"""
        return User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='adminpass',
            is_superuser=True
        )

    @pytest.fixture
    def test_officer(self):
        """Test officer fixture"""
        return RajOfficer.objects.create(
            user_id='RAJKSNOFSR88888',
            name='Pytest Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE'
        )

    def test_officer_registration_flow(self, api_client, admin_user):
        """Test complete officer registration flow"""
        api_client.force_authenticate(user=admin_user)

        officer_data = {
            'user_id': 'RAJKSNOFSR77777',
            'name': 'Flow Test Officer',
            'user_name': 'flowtestofficer',
            'mobile_number': '9777777777',
            'email': 'flowtest@example.com',
            'address': 'Flow Test Address',
            'gender': Gender.MALE.value,
            'aadhar_number': '777777777777',
            'designation': 'AGRICULTURE_OFFICER',
            'department': 'AGRICULTURE',
            'role': 'FIELD_OFFICER',
            'password': 'flowtest123',
            'confirm_password': 'flowtest123'
        }

        with patch('Raj_Officer.views.BlockchainAPIService') as mock_blockchain:
            mock_service = Mock()
            mock_service.add_department_officer.return_value = {
                'transaction_hash': '0xabcdef123456'
            }
            mock_blockchain.return_value = mock_service

            # Register officer
            response = api_client.post('/admin/register-officer', officer_data, format='json')
            assert response.status_code == status.HTTP_201_CREATED

            # Verify officer exists
            assert RajOfficer.objects.filter(user_id='RAJKSNOFSR77777').exists()

            # List officers
            response = api_client.get('/admin/officers/')
            assert response.status_code == status.HTTP_200_OK
            assert len(response.data['data']) == 1

            # Get officer detail
            response = api_client.get('/admin/officers?officer_id=RAJKSNOFSR77777')
            assert response.status_code == status.HTTP_200_OK
            assert response.data['data']['name'] == 'Flow Test Officer'

            # Update officer
            update_data = {'name': 'Updated Flow Officer'}
            response = api_client.put(
                '/admin/officers/update?officer_id=RAJKSNOFSR77777',
                update_data,
                format='json'
            )
            assert response.status_code == status.HTTP_200_OK

            # Delete officer
            response = api_client.delete('/admin/officers/delete?officer_id=RAJKSNOFSR77777')
            assert response.status_code == status.HTTP_204_NO_CONTENT

            # Verify officer is deleted
            assert not RajOfficer.objects.filter(user_id='RAJKSNOFSR77777').exists()

    @pytest.mark.parametrize("user_type,expected_status", [
        ('admin', status.HTTP_201_CREATED),
        ('regular', status.HTTP_403_FORBIDDEN),
        ('anonymous', status.HTTP_401_UNAUTHORIZED),
    ])
    def test_officer_registration_permissions(self, api_client, user_type, expected_status):
        """Test officer registration with different user types"""
        officer_data = {
            'user_id': 'RAJKSNOFSR66666',
            'name': 'Permission Test Officer',
            'designation': 'AGRICULTURE_OFFICER',
            'department': 'AGRICULTURE',
            'password': 'test123',
            'confirm_password': 'test123'
        }

        if user_type == 'admin':
            admin_user = User.objects.create_user(
                username='admin', is_superuser=True, password='pass'
            )
            api_client.force_authenticate(user=admin_user)
        elif user_type == 'regular':
            regular_user = User.objects.create_user(
                username='regular', password='pass'
            )
            api_client.force_authenticate(user=regular_user)
        # For 'anonymous', don't authenticate

        with patch('Raj_Officer.views.BlockchainAPIService'):
            response = api_client.post('/admin/register-officer', officer_data, format='json')
            assert response.status_code == expected_status