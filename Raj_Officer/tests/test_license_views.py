"""
Unit and Integration tests for License-related views
"""
import json
import pytest
from datetime import datetime, timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from seed_license.models import License, BlockchainTransaction
from Raj_Officer.models import RajOfficer

User = get_user_model()


class LicenseViewsTestCase(APITestCase):
    """Base test case for License views"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create test users
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass',
            is_superuser=True
        )

        self.officer_user = User.objects.create_user(
            username='officer',
            email='officer@example.com',
            password='officerpass'
        )

        # Create test officer
        self.test_officer = RajOfficer.objects.create(
            user_id='RAJKSNOFSR12345',
            name='Test Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE'
        )

        # Create test licenses
        self.license1 = License.objects.create(
            license_id=1,
            license_type='SEED_PRODUCTION',
            crop_type='WHEAT',
            seed_variety='HD-2967',
            quantity=100.0,
            location='Jaipur, Rajasthan',
            quality_parameters='Grade A',
            source='Local Farm',
            aadhaar='123456789012',
            blockchain_tx_id='0xabcdef123456',
            status='APPLIED',
            applicant='Test_farmer',
        )

        self.license2 = License.objects.create(
            license_id=2,
            license_type='SEED_DISTRIBUTION',
            crop_type='RICE',
            seed_variety='Basmati-370',
            quantity=50.0,
            location='Udaipur, Rajasthan',
            quality_parameters='Grade B',
            source='Certified Agency',
            aadhaar='987654321098',
            blockchain_tx_id='0x123456abcdef',
            status='APPROVED',
            applicant='Another Farmer'
        )

    def authenticate_admin(self):
        """Helper method to authenticate as admin"""
        self.client.force_authenticate(user=self.admin_user)

    def authenticate_officer(self):
        """Helper method to authenticate as officer"""
        self.client.force_authenticate(user=self.officer_user)


class TestDepartmentLicensesView(LicenseViewsTestCase):
    """Test cases for department_licenses_view"""

    def test_list_licenses_success(self):
        """Test successful license listing"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 2)
        self.assertEqual(len(response.data['data']['licenses']), 2)

    def test_list_licenses_with_pagination(self):
        """Test license listing with pagination"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses?page=1&limit=1')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 2)
        self.assertEqual(len(response.data['data']['licenses']), 1)
        self.assertEqual(response.data['data']['page'], 1)
        self.assertEqual(response.data['data']['limit'], 1)

    def test_list_licenses_with_status_filter(self):
        """Test license listing with status filter"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses?status=APPROVED')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['licenses'][0]['status'], 'APPROVED')

    def test_list_licenses_with_type_filter(self):
        """Test license listing with type filter"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses?type=SEED_PRODUCTION')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['licenses'][0]['license_type'], 'SEED_PRODUCTION')

    def test_list_licenses_with_district_filter(self):
        """Test license listing with district filter"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses?district=Jaipur')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertIn('Jaipur', response.data['data']['licenses'][0]['location'])

    def test_list_licenses_with_date_filters(self):
        """Test license listing with date filters"""
        self.authenticate_admin()

        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        response = self.client.get(
            f'/department/licenses?from_date={yesterday}&to_date={tomorrow}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 2)

    def test_list_licenses_invalid_date_format(self):
        """Test license listing with invalid date format"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses?from_date=invalid-date')

        # Should still return results, just ignore invalid date
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_licenses_unauthenticated(self):
        """Test license listing without authentication"""
        response = self.client.get('/department/licenses')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_licenses_empty_result(self):
        """Test license listing with filters that return no results"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses?status=NONEXISTENT_STATUS')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 0)
        self.assertEqual(len(response.data['data']['licenses']), 0)


class TestDepartmentLicenseDetailView(LicenseViewsTestCase):
    """Test cases for department_license_detail_view"""

    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_get_license_detail_success(self, mock_handler):
        """Test successful license detail retrieval"""
        # Mock handler response
        mock_handler_instance = Mock()
        mock_handler_instance.get_license_summary.return_value = [
            1,  # license_id
            '0x1234567890123456789012345678901234567890',  # farmer_address
            'Test Farmer',  # name
            'Jaipur, Rajasthan',  # location
            'SEED_PRODUCTION',  # license_type
            'APPLIED',  # status
            1640995200,  # submitted_at (timestamp)
            None,  # approval_date
            None,  # expiry_date
            True,  # is_active
            ['HD-2967', 'WHEAT', 100.0, 'Grade A', 'Local Farm']  # seed_details
        ]
        mock_handler.return_value = mock_handler_instance

        self.authenticate_admin()

        response = self.client.get('/department/licenses/?id=1')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['license_id'], 1)
        self.assertEqual(response.data['data']['name'], 'Test Farmer')
        self.assertEqual(response.data['data']['license_type'], 'SEED_PRODUCTION')
        self.assertIn('seed_details', response.data['data'])

    def test_get_license_detail_missing_id(self):
        """Test license detail retrieval without ID parameter"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or missing 'status'", response.data['err'])

    def test_update_license_status_invalid_status(self):
        """Test license status update with invalid status value"""
        self.authenticate_admin()

        update_data = {
            'status': 10,  # Invalid status (> 7)
            'remarks': 'Some remarks'
        }

        response = self.client.put(
            f'/department/licenses/{self.license1.license_id}/status/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or missing 'status'", response.data['err'])

    def test_update_license_status_rejection_without_remarks(self):
        """Test license status update for rejection without remarks"""
        self.authenticate_admin()

        update_data = {
            'status': 5,  # REJECTED
            # Missing remarks
        }

        response = self.client.put(
            f'/department/licenses/{self.license1.license_id}/status/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Remarks required for rejection/revocation', response.data['err'])

    def test_update_license_status_revocation_without_remarks(self):
        """Test license status update for revocation without remarks"""
        self.authenticate_admin()

        update_data = {
            'status': 6,  # REVOKED
            # Missing remarks
        }

        response = self.client.put(
            f'/department/licenses/{self.license1.license_id}/status/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Remarks required for rejection/revocation', response.data['err'])

    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_update_license_status_handler_exception(self, mock_handler):
        """Test license status update with handler exception"""
        # Mock handler to raise exception
        mock_handler_instance = Mock()
        mock_handler_instance.update_license_status.side_effect = Exception("Handler error")
        mock_handler.return_value = mock_handler_instance

        self.authenticate_admin()

        update_data = {
            'status': 4,
            'remarks': 'Test remarks'
        }

        response = self.client.put(
            f'/department/licenses/{self.license1.license_id}/status/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Failed to update license status', response.data['err'])


class TestVerifyLicenseDocuments(LicenseViewsTestCase):
    """Test cases for verify_license_documents view"""

    def setUp(self):
        super().setUp()
        # Add blockchain wallet to officer user
        self.officer_user.blockchain_wallet = Mock()
        self.officer_user.blockchain_wallet.address = '0x1234567890123456789012345678901234567890'

    @patch('Raj_Officer.views.BlockchainAPIService')
    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_verify_documents_success(self, mock_handler, mock_blockchain_service):
        """Test successful document verification"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.get_officer_role.return_value = {'is_authorized': True}
        mock_blockchain_service.return_value = mock_service

        # Mock handler
        mock_handler_instance = Mock()
        mock_handler_instance.update_license_status.return_value = True
        mock_handler.return_value = mock_handler_instance

        self.authenticate_officer()

        verify_data = {
            'documents': ['doc1', 'doc2', 'doc3'],
            'verification_notes': 'All documents verified successfully'
        }

        response = self.client.post(
            f'/department/licenses/{self.license1.license_id}/verify-documents/',
            verify_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['verified_documents'], ['doc1', 'doc2', 'doc3'])
        self.assertIn('verified_at', response.data['data'])

    def test_verify_documents_missing_documents(self):
        """Test document verification without documents list"""
        self.authenticate_officer()

        verify_data = {
            'verification_notes': 'Some notes'
        }

        response = self.client.post(
            f'/department/licenses/{self.license1.license_id}/verify-documents/',
            verify_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('At least one document ID is required', response.data['err'])

    def test_verify_documents_no_blockchain_wallet(self):
        """Test document verification without blockchain wallet"""
        # Remove blockchain wallet
        self.officer_user.blockchain_wallet = None
        self.authenticate_officer()

        verify_data = {
            'documents': ['doc1', 'doc2']
        }

        response = self.client.post(
            f'/department/licenses/{self.license1.license_id}/verify-documents/',
            verify_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('User has no associated blockchain wallet', response.data['err'])

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_verify_documents_unauthorized_officer(self, mock_blockchain_service):
        """Test document verification by unauthorized officer"""
        # Mock blockchain service to return unauthorized
        mock_service = Mock()
        mock_service.get_officer_role.return_value = {'is_authorized': False}
        mock_blockchain_service.return_value = mock_service

        self.authenticate_officer()

        verify_data = {
            'documents': ['doc1', 'doc2']
        }

        response = self.client.post(
            f'/department/licenses/{self.license1.license_id}/verify-documents/',
            verify_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('User is not an authorized officer', response.data['err'])


class TestRecordFieldInspection(LicenseViewsTestCase):
    """Test cases for record_field_inspection view"""

    def setUp(self):
        super().setUp()
        # Add blockchain wallet to officer user
        self.officer_user.blockchain_wallet = Mock()
        self.officer_user.blockchain_wallet.address = '0x1234567890123456789012345678901234567890'

    @patch('Raj_Officer.views.BlockchainAPIService')
    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_record_inspection_success(self, mock_handler, mock_blockchain_service):
        """Test successful field inspection recording"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.get_officer_role.return_value = {'is_authorized': True}
        mock_blockchain_service.return_value = mock_service

        # Mock handler
        mock_handler_instance = Mock()
        mock_handler_instance.update_license_status.return_value = True
        mock_handler.return_value = mock_handler_instance

        self.authenticate_officer()

        inspection_data = {
            'inspection_data': {
                'soil_quality': 'Good',
                'irrigation': 'Adequate',
                'seed_storage': 'Proper'
            },
            'inspection_notes': 'Field inspection completed successfully'
        }

        response = self.client.post(
            f'/department/licenses/{self.license1.license_id}/field-inspection/',
            inspection_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('inspection_id', response.data['data'])
        self.assertIn('inspection_date', response.data['data'])

    def test_record_inspection_missing_data(self):
        """Test field inspection recording without inspection data"""
        self.authenticate_officer()

        inspection_data = {
            'inspection_notes': 'Some notes'
        }

        response = self.client.post(
            f'/department/licenses/{self.license1.license_id}/field-inspection/',
            inspection_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Inspection data is required', response.data['err'])


class TestRevokeLicense(LicenseViewsTestCase):
    """Test cases for revoke_license view"""

    def setUp(self):
        super().setUp()
        # Add blockchain wallet to admin user
        self.admin_user.blockchain_wallet = Mock()
        self.admin_user.blockchain_wallet.address = '0x1234567890123456789012345678901234567890'

    @patch('Raj_Officer.views.BlockchainAPIService')
    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_revoke_license_success(self, mock_handler, mock_blockchain_service):
        """Test successful license revocation"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.get_officer_role.return_value = {
            'role_id': 0,  # Agriculture Officer
            'is_authorized': True
        }
        mock_blockchain_service.return_value = mock_service

        # Mock handler
        mock_handler_instance = Mock()
        mock_handler_instance.update_license_status.return_value = True
        mock_handler.return_value = mock_handler_instance

        self.authenticate_admin()

        revoke_data = {
            'reason': 'Violation of terms and conditions',
            'additional_notes': 'Found irregularities during inspection'
        }

        response = self.client.post(
            f'/department/licenses/{self.license2.license_id}/revoke/',
            revoke_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['status'], 'REVOKED')
        self.assertEqual(response.data['data']['reason'], 'Violation of terms and conditions')

    def test_revoke_license_missing_reason(self):
        """Test license revocation without reason"""
        self.authenticate_admin()

        revoke_data = {
            'additional_notes': 'Some notes'
        }

        response = self.client.post(
            f'/department/licenses/{self.license2.license_id}/revoke/',
            revoke_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Reason is required for revocation', response.data['err'])

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_revoke_license_insufficient_permissions(self, mock_blockchain_service):
        """Test license revocation with insufficient permissions"""
        # Mock blockchain service to return unauthorized role
        mock_service = Mock()
        mock_service.get_officer_role.return_value = {
            'role_id': 3,  # Not authorized for revocation
            'is_authorized': True
        }
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        revoke_data = {
            'reason': 'Test revocation'
        }

        response = self.client.post(
            f'/department/licenses/{self.license2.license_id}/revoke/',
            revoke_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('User does not have permission to revoke licenses', response.data['err'])


class TestInspectionViews(LicenseViewsTestCase):
    """Test cases for inspection-related views"""

    def setUp(self):
        super().setUp()
        # Add blockchain wallet to officer user
        self.officer_user.blockchain_wallet = Mock()
        self.officer_user.blockchain_wallet.address = '0x1234567890123456789012345678901234567890'

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_inspection_check_in_success(self, mock_blockchain_service):
        """Test successful inspection check-in"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.record_inspection_start.return_value = {
            'transaction_hash': '0xabcdef123456'
        }
        mock_blockchain_service.return_value = mock_service

        self.authenticate_officer()

        checkin_data = {
            'license_id': self.license1.license_id,
            'location': {
                'latitude': 26.9124,
                'longitude': 75.7873
            },
            'device_info': {
                'device_type': 'mobile',
                'os': 'android'
            }
        }

        response = self.client.post(
            '/inspections/check-in/',
            checkin_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('inspection_id', response.data['data'])
        self.assertIn('check_in_time', response.data['data'])

    def test_inspection_check_in_missing_fields(self):
        """Test inspection check-in with missing required fields"""
        self.authenticate_officer()

        checkin_data = {
            'license_id': self.license1.license_id
            # Missing location
        }

        response = self.client.post(
            '/inspections/check-in/',
            checkin_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Both license_id and location are required', response.data['err'])

    @patch('Raj_Officer.views.default_storage')
    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_upload_inspection_photo_success(self, mock_blockchain_service, mock_storage):
        """Test successful inspection photo upload"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.record_inspection_photo.return_value = {
            'transaction_hash': '0xabcdef123456'
        }
        mock_blockchain_service.return_value = mock_service

        # Mock storage
        mock_storage.save.return_value = 'inspections/INSP-1-123456/photo.jpg'
        mock_storage.url.return_value = '/media/inspections/INSP-1-123456/photo.jpg'

        self.authenticate_officer()

        # Create mock file
        from django.core.files.uploadedfile import SimpleUploadedFile
        photo_file = SimpleUploadedFile(
            "test_photo.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )

        upload_data = {
            'inspection_id': 'INSP-1-123456',
            'photo_type': 'field_overview',
            'location': json.dumps({'lat': 26.9124, 'lng': 75.7873}),
            'caption': 'Field overview photo'
        }

        response = self.client.post(
            '/inspections/upload-photo/',
            {**upload_data, 'photo': photo_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('photo_id', response.data['data'])
        self.assertIn('photo_url', response.data['data'])

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_complete_inspection_success(self, mock_blockchain_service):
        """Test successful inspection completion"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.complete_inspection.return_value = {
            'transaction_hash': '0xabcdef123456'
        }
        mock_blockchain_service.return_value = mock_service

        self.authenticate_officer()

        completion_data = {
            'inspection_id': 'INSP-1-123456',
            'result': 'PASSED',
            'remarks': 'All parameters meet the required standards',
            'location': {
                'latitude': 26.9124,
                'longitude': 75.7873
            },
            'checklist': {
                'soil_quality': 'good',
                'irrigation': 'adequate',
                'storage': 'proper'
            }
        }

        response = self.client.post(
            '/inspections/complete/',
            completion_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['result'], 'PASSED')
        self.assertIn('completion_time', response.data['data'])


@pytest.mark.django_db
class TestLicenseViewsPytest:
    """Pytest version of license view tests"""

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
    def test_license(self, admin_user):
        """Test license fixture"""
        return License.objects.create(
            license_id=999,
            license_type='SEED_PRODUCTION',
            crop_type='WHEAT',
            seed_variety='HD-2967',
            quantity=100.0,
            location='Test Location',
            quality_parameters='Grade A',
            source='Test Source',
            aadhaar='123456789012',
            blockchain_tx_id='0xtest123456',
            status='APPLIED',
            applicant=admin_user,
            name='Test Applicant'
        )

    def test_license_listing_flow(self, api_client, admin_user, test_license):
        """Test complete license listing flow"""
        api_client.force_authenticate(user=admin_user)

        # Test basic listing
        response = api_client.get('/department/licenses')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['total'] == 1

        # Test with filters
        response = api_client.get('/department/licenses?status=APPLIED')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['licenses'][0]['status'] == 'APPLIED'

        # Test with pagination
        response = api_client.get('/department/licenses?page=1&limit=5')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['page'] == 1
        assert response.data['data']['limit'] == 5

    @pytest.mark.parametrize("status_code,remarks_required", [
        (0, False),  # APPLIED
        (1, False),  # DOCUMENTS_VERIFIED
        (4, False),  # APPROVED
        (5, True),  # REJECTED
        (6, True),  # REVOKED
    ])
    def test_license_status_update_validation(self, api_client, admin_user, test_license, status_code,
                                              remarks_required):
        """Test license status update validation"""
        api_client.force_authenticate(user=admin_user)

        update_data = {'status': status_code}
        if not remarks_required:
            update_data['remarks'] = 'Test remarks'

        with patch('Raj_Officer.views.SeedLicenseHandler') as mock_handler:
            mock_handler_instance = Mock()
            mock_receipt = Mock()
            mock_receipt.transactionHash.hex.return_value = '0xtest123'
            mock_receipt.blockNumber = 12345
            mock_handler_instance.update_license_status.return_value = mock_receipt
            mock_handler.return_value = mock_handler_instance

            response = api_client.put(
                f'/department/licenses/{test_license.license_id}/status/',
                update_data,
                format='json'
            )

            if remarks_required:
                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert 'Remarks required' in response.data['err']
            else:
                assert response.status_code == status.HTTP_200_OK
                assert response.data['data']['status'] == status_code
                self.assertIn("Missing required query parameter: 'id'", response.data['err'])

    def test_get_license_detail_invalid_id(self):
        """Test license detail retrieval with invalid ID"""
        self.authenticate_admin()

        response = self.client.get('/department/licenses/?id=invalid')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('License ID must be a valid integer', response.data['err'])

    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_get_license_detail_not_found(self, mock_handler):
        """Test license detail retrieval for non-existent license"""
        # Mock handler to return None
        mock_handler_instance = Mock()
        mock_handler_instance.get_license_summary.return_value = None
        mock_handler.return_value = mock_handler_instance

        self.authenticate_admin()

        response = self.client.get('/department/licenses/?id=999')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('No license data found', response.data['err'])

    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_get_license_detail_handler_exception(self, mock_handler):
        """Test license detail retrieval with handler exception"""
        # Mock handler to raise exception
        mock_handler_instance = Mock()
        mock_handler_instance.get_license_summary.side_effect = Exception("Handler error")
        mock_handler.return_value = mock_handler_instance

        self.authenticate_admin()

        response = self.client.get('/department/licenses/?id=1')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Failed to retrieve license summary', response.data['err'])


class TestDepartmentLicenseStatusView(LicenseViewsTestCase):
    """Test cases for department_license_status_view"""

    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_update_license_status_success(self, mock_handler):
        """Test successful license status update"""
        # Mock handler response
        mock_handler_instance = Mock()
        mock_receipt = Mock()
        mock_receipt.transactionHash.hex.return_value = '0xabcdef123456'
        mock_receipt.blockNumber = 12345
        mock_handler_instance.update_license_status.return_value = mock_receipt
        mock_handler.return_value = mock_handler_instance

        self.authenticate_admin()

        update_data = {
            'status': 4,  # APPROVED
            'remarks': 'Application approved after review'
        }

        response = self.client.put(
            f'/department/licenses/{self.license1.license_id}/status/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['status'], 4)
        self.assertEqual(response.data['data']['blockchain_tx_id'], '0xabcdef123456')

        # Verify handler was called with correct parameters
        mock_handler_instance.update_license_status.assert_called_once()

    def test_update_license_status_missing_status(self):
        """Test license status update without status parameter"""
        self.authenticate_admin()

        update_data = {'remarks': 'Some remarks'}

        response = self.client.put(
            f'/department/licenses/{self.license1.license_id}/status/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)