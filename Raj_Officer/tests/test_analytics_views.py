"""
Unit and Integration tests for Analytics views
"""
import pytest
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import Mock, patch
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from seed_license.models import License, BlockchainTransaction
from Raj_Officer.models import RajOfficer

User = get_user_model()


class AnalyticsViewsTestCase(APITestCase):
    """Base test case for Analytics views"""

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

        # Create test users for license applicants
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='userpass1'
        )

        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='userpass2'
        )

        # Create test licenses with different statuses, types, and dates
        now = timezone.now()
        last_month = now - timedelta(days=30)

        self.licenses = [
            License.objects.create(
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
                applicant=self.user1,
                submitted_at=now
            ),
            License.objects.create(
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
                applicant=self.user2,
                submitted_at=now
            ),
            License.objects.create(
                license_id=3,
                license_type='SEED_PRODUCTION',
                crop_type='WHEAT',
                seed_variety='PBW-343',
                quantity=75.0,
                location='Jodhpur, Rajasthan',
                quality_parameters='Grade A',
                source='Government Agency',
                aadhaar='456789123456',
                blockchain_tx_id='0x789abc123def',
                status='REJECTED',
                applicant=self.user1,
                submitted_at=last_month
            ),
            License.objects.create(
                license_id=4,
                license_type='SEED_DISTRIBUTION',
                crop_type='COTTON',
                seed_variety='BT-Cotton',
                quantity=200.0,
                location='Kota, Rajasthan',
                quality_parameters='Grade A',
                source='Private Company',
                aadhaar='789123456789',
                blockchain_tx_id='0xdef456789abc',
                status='DOCUMENTS_VERIFIED',
                applicant=self.user2,
                submitted_at=last_month
            ),
            License.objects.create(
                license_id=5,
                license_type='SEED_CERTIFICATION',
                crop_type='MUSTARD',
                seed_variety='Pusa-Bold',
                quantity=25.0,
                location='Bikaner, Rajasthan',
                quality_parameters='Grade B',
                source='Research Institute',
                aadhaar='321654987321',
                blockchain_tx_id='0x321cba654fed',
                status='FIELD_INSPECTION_COMPLETED',
                applicant=self.user1,
                submitted_at=now
            )
        ]

        # Create test blockchain transactions
        self.create_test_transactions()

    def create_test_transactions(self):
        """Create test blockchain transactions"""
        for i, license in enumerate(self.licenses):
            BlockchainTransaction.objects.create(
                tx_hash=f'0x{i:064x}',
                block_number=12345 + i,
                status='CONFIRMED',
                timestamp=license.submitted_at,
                action_type='LICENSE_APPLY',
                license=license,
                created_by=license.applicant
            )

    def authenticate_admin(self):
        """Helper method to authenticate as admin"""
        self.client.force_authenticate(user=self.admin_user)


class TestLicenseCountsByStatus(AnalyticsViewsTestCase):
    """Test cases for license_counts_by_status view"""

    def test_get_license_counts_by_status_success(self):
        """Test successful retrieval of license counts by status"""
        self.authenticate_admin()

        response = self.client.get('/analytics/licenses/by-status')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 5)

        # Check that counts are returned
        counts = response.data['data']['counts']
        self.assertIsInstance(counts, list)
        self.assertTrue(len(counts) > 0)

        # Verify specific status counts
        status_dict = {item['status']: item['count'] for item in counts}
        self.assertEqual(status_dict.get('APPLIED', 0), 1)
        self.assertEqual(status_dict.get('APPROVED', 0), 1)
        self.assertEqual(status_dict.get('REJECTED', 0), 1)
        self.assertEqual(status_dict.get('DOCUMENTS_VERIFIED', 0), 1)
        self.assertEqual(status_dict.get('FIELD_INSPECTION_COMPLETED', 0), 1)

    def test_get_license_counts_by_status_with_date_filter(self):
        """Test license counts by status with date filters"""
        self.authenticate_admin()

        today = timezone.now().date()
        response = self.client.get(f'/analytics/licenses/by-status?from_date={today}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only licenses from today (3 licenses)
        self.assertEqual(response.data['data']['total'], 3)

    def test_get_license_counts_by_status_with_district_filter(self):
        """Test license counts by status with district filter"""
        self.authenticate_admin()

        response = self.client.get('/analytics/licenses/by-status?district=Jaipur')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only licenses from Jaipur (1 license)
        self.assertEqual(response.data['data']['total'], 1)

    def test_get_license_counts_by_status_with_license_type_filter(self):
        """Test license counts by status with license type filter"""
        self.authenticate_admin()

        response = self.client.get('/analytics/licenses/by-status?license_type=SEED_PRODUCTION')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only SEED_PRODUCTION licenses (2 licenses)
        self.assertEqual(response.data['data']['total'], 2)

    def test_get_license_counts_by_status_unauthenticated(self):
        """Test license counts by status without authentication"""
        response = self.client.get('/analytics/licenses/by-status')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_license_counts_by_status_invalid_date(self):
        """Test license counts by status with invalid date format"""
        self.authenticate_admin()

        response = self.client.get('/analytics/licenses/by-status?from_date=invalid-date')

        # Should handle invalid date gracefully and return all results
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 5)


class TestLicenseCountsByType(AnalyticsViewsTestCase):
    """Test cases for license_counts_by_type view"""

    def test_get_license_counts_by_type_success(self):
        """Test successful retrieval of license counts by type"""
        self.authenticate_admin()

        response = self.client.get('/analytics/licenses/by-type')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 5)

        # Check that counts are returned
        counts = response.data['data']['counts']
        self.assertIsInstance(counts, list)
        self.assertTrue(len(counts) > 0)

        # Verify specific type counts
        type_dict = {item['license_type']: item['count'] for item in counts}
        self.assertEqual(type_dict.get('SEED_PRODUCTION', 0), 2)
        self.assertEqual(type_dict.get('SEED_DISTRIBUTION', 0), 2)
        self.assertEqual(type_dict.get('SEED_CERTIFICATION', 0), 1)

    def test_get_license_counts_by_type_with_status_filter(self):
        """Test license counts by type with status filter"""
        self.authenticate_admin()

        response = self.client.get('/analytics/licenses/by-type?status=APPROVED')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only approved licenses (1 license)
        self.assertEqual(response.data['data']['total'], 1)

        counts = response.data['data']['counts']
        self.assertEqual(len(counts), 1)
        self.assertEqual(counts[0]['license_type'], 'SEED_DISTRIBUTION')

    def test_get_license_counts_by_type_with_multiple_filters(self):
        """Test license counts by type with multiple filters"""
        self.authenticate_admin()

        today = timezone.now().date()
        response = self.client.get(
            f'/analytics/licenses/by-type?from_date={today}&district=Jaipur'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 1)


class TestMonthlyLicenseStats(AnalyticsViewsTestCase):
    """Test cases for monthly_license_stats view"""

    def test_get_monthly_stats_success(self):
        """Test successful retrieval of monthly license statistics"""
        self.authenticate_admin()

        current_year = timezone.now().year
        response = self.client.get(f'/reports/licenses/monthly?year={current_year}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['year'], current_year)
        self.assertEqual(response.data['data']['total'], 5)

        # Check monthly stats structure
        monthly_stats = response.data['data']['monthly_stats']
        self.assertEqual(len(monthly_stats), 12)  # 12 months

        # Each month should have required fields
        for month_stat in monthly_stats:
            self.assertIn('month', month_stat)
            self.assertIn('month_name', month_stat)
            self.assertIn('applications', month_stat)
            self.assertIn('approved', month_stat)
            self.assertIn('rejected', month_stat)
            self.assertIn('pending', month_stat)

    def test_get_monthly_stats_with_filters(self):
        """Test monthly statistics with filters"""
        self.authenticate_admin()

        current_year = timezone.now().year
        response = self.client.get(
            f'/reports/licenses/monthly?year={current_year}&license_type=SEED_PRODUCTION'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only SEED_PRODUCTION licenses (2 licenses)
        self.assertEqual(response.data['data']['total'], 2)

    def test_get_monthly_stats_default_year(self):
        """Test monthly statistics without specifying year (should use current year)"""
        self.authenticate_admin()

        response = self.client.get('/reports/licenses/monthly')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['year'], timezone.now().year)

    def test_get_monthly_stats_different_year(self):
        """Test monthly statistics for a different year (should return empty)"""
        self.authenticate_admin()

        different_year = timezone.now().year - 1
        response = self.client.get(f'/reports/licenses/monthly?year={different_year}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['year'], different_year)
        self.assertEqual(response.data['data']['total'], 0)


class TestLicensesByDistrict(AnalyticsViewsTestCase):
    """Test cases for licenses_by_district view"""

    def test_get_licenses_by_district_success(self):
        """Test successful retrieval of license statistics by district"""
        self.authenticate_admin()

        response = self.client.get('/reports/licenses/by-district')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 5)

        # Check district stats structure
        district_stats = response.data['data']['district_stats']
        self.assertIsInstance(district_stats, list)
        self.assertTrue(len(district_stats) > 0)

        # Each district should have required fields
        for district_stat in district_stats:
            self.assertIn('district', district_stat)
            self.assertIn('applications', district_stat)
            self.assertIn('approved', district_stat)
            self.assertIn('rejected', district_stat)
            self.assertIn('pending', district_stat)

        # Verify some expected districts
        districts = [stat['district'] for stat in district_stats]
        self.assertIn('Rajasthan', districts)  # From location parsing

    def test_get_licenses_by_district_with_date_filter(self):
        """Test district statistics with date filters"""
        self.authenticate_admin()

        today = timezone.now().date()
        response = self.client.get(f'/reports/licenses/by-district?from_date={today}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only licenses from today
        self.assertEqual(response.data['data']['total'], 3)

    def test_get_licenses_by_district_with_status_filter(self):
        """Test district statistics with status filter"""
        self.authenticate_admin()

        response = self.client.get('/reports/licenses/by-district?status=APPROVED')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 1)

    def test_get_licenses_by_district_with_license_type_filter(self):
        """Test district statistics with license type filter"""
        self.authenticate_admin()

        response = self.client.get('/reports/licenses/by-district?license_type=SEED_PRODUCTION')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total'], 2)


class TestOfficerPerformanceMetrics(AnalyticsViewsTestCase):
    """Test cases for officer_performance_metrics view"""

    def setUp(self):
        super().setUp()

        # Create test officers
        self.officer1 = RajOfficer.objects.create(
            user_id='RAJKSNOFSR11111',
            name='Officer 1',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE'
        )

        self.officer2 = RajOfficer.objects.create(
            user_id='RAJKSNOFSR22222',
            name='Officer 2',
            designation='DISTRICT_COLLECTOR',
            department='REVENUE'
        )

        # Create additional blockchain transactions for officer actions
        self.create_officer_transactions()

    def create_officer_transactions(self):
        """Create test transactions for officer performance"""
        now = timezone.now()

        # Create status update transactions
        for i, license in enumerate(self.licenses[:2]):
            BlockchainTransaction.objects.create(
                tx_hash=f'0x{(100 + i):064x}',
                block_number=12350 + i,
                status='CONFIRMED',
                timestamp=now + timedelta(hours=i),
                action_type='STATUS_UPDATE',
                license=license,
                created_by=self.admin_user  # Using admin as officer for test
            )

    @patch('Raj_Officer.views.BlockchainAPIService')
    @patch('Raj_Officer.views.SeedLicenseHandler')
    def test_get_officer_performance_success(self, mock_handler, mock_blockchain_service):
        """Test successful retrieval of officer performance metrics"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.get_officer_role.return_value = {
            'role_name': 'AGRICULTURE_OFFICER'
        }
        mock_blockchain_service.return_value = mock_service

        # Mock handler
        mock_handler_instance = Mock()
        mock_handler_instance.get_license_summary.return_value = [
            1, '0x123', 'Farmer', 'Location', 'SEED_PRODUCTION',
            'APPLIED', 1640995200, None, None, 4, ['variety', 'crop', 100, 'grade', 'source']
        ]
        mock_handler.return_value = mock_handler_instance

        self.authenticate_admin()

        response = self.client.get('/reports/officers/performance')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_officers', response.data['data'])
        self.assertIn('officer_metrics', response.data['data'])

        # Check officer metrics structure
        if response.data['data']['officer_metrics']:
            metrics = response.data['data']['officer_metrics'][0]
            self.assertIn('officer_id', metrics)
            self.assertIn('applications_processed', metrics)
            self.assertIn('applications_approved', metrics)
            self.assertIn('applications_rejected', metrics)
            self.assertIn('average_processing_time', metrics)
            self.assertIn('inspections_conducted', metrics)

    @patch('Raj_Officer.views.BlockchainAPIService')
    def test_get_officer_performance_with_officer_filter(self, mock_blockchain_service):
        """Test officer performance with specific officer filter"""
        # Mock blockchain service
        mock_service = Mock()
        mock_service.get_officer_role.return_value = {
            'role_name': 'AGRICULTURE_OFFICER'
        }
        mock_blockchain_service.return_value = mock_service

        self.authenticate_admin()

        officer_address = '0x1234567890123456789012345678901234567890'
        response = self.client.get(f'/reports/officers/performance?officer_id={officer_address}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_officer_performance_invalid_address(self):
        """Test officer performance with invalid address format"""
        self.authenticate_admin()

        response = self.client.get('/reports/officers/performance?officer_id=invalid_address')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid officer address format', response.data['err'])

    def test_get_officer_performance_with_date_filters(self):
        """Test officer performance with date filters"""
        self.authenticate_admin()

        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        response = self.client.get(
            f'/reports/officers/performance?from_date={yesterday}&to_date={today}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_officer_performance_unauthenticated(self):
        """Test officer performance without authentication"""
        response = self.client.get('/reports/officers/performance')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class TestAnalyticsViewsPytest:
    """Pytest version of analytics view tests"""

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
    def sample_licenses(self, admin_user):
        """Sample licenses fixture"""
        licenses = []
        statuses = ['APPLIED', 'APPROVED', 'REJECTED', 'DOCUMENTS_VERIFIED']
        types = ['SEED_PRODUCTION', 'SEED_DISTRIBUTION']

        for i in range(10):
            license = License.objects.create(
                license_id=1000 + i,
                license_type=types[i % 2],
                crop_type='WHEAT',
                seed_variety=f'Variety-{i}',
                quantity=100.0 + i,
                location=f'District-{i % 3}, Rajasthan',
                quality_parameters='Grade A',
                source='Test Source',
                aadhaar=f'{1234567890 + i:02d}',
                blockchain_tx_id=f'0x{i:064x}',
                status=statuses[i % 4],
                applicant=admin_user
            )
            licenses.append(license)
        return licenses

    def test_analytics_endpoint_responses(self, api_client, admin_user, sample_licenses):
        """Test all analytics endpoints return valid responses"""
        api_client.force_authenticate(user=admin_user)

        endpoints = [
            '/api/analytics/licenses/by-status',
            '/api/analytics/licenses/by-type',
            '/api/reports/licenses/monthly',
            '/api/reports/licenses/by-district',
            '/api/reports/officers/performance'
        ]

        with patch('Raj_Officer.views.BlockchainAPIService') as mock_blockchain, \
                patch('Raj_Officer.views.SeedLicenseHandler') as mock_handler:
            # Mock blockchain service
            mock_service = Mock()
            mock_service.get_officer_role.return_value = {'role_name': 'OFFICER'}
            mock_blockchain.return_value = mock_service

            # Mock handler
            mock_handler_instance = Mock()
            mock_handler_instance.get_license_summary.return_value = [
                1, '0x123', 'Farmer', 'Location', 'TYPE', 'STATUS',
                1640995200, None, None, 4, ['variety', 'crop', 100, 'grade', 'source']
            ]
            mock_handler.return_value = mock_handler_instance

            for endpoint in endpoints:
                response = api_client.get(endpoint)
                assert response.status_code == status.HTTP_200_OK
                assert 'data' in response.data

    @pytest.mark.parametrize("filter_param,filter_value,expected_count", [
        ('status', 'APPLIED', 3),  # 10 licenses, every 4th is APPLIED (0,4,8)
        ('license_type', 'SEED_PRODUCTION', 5),  # Every other license
        ('district', 'District-0', 4),  # Every 3rd district (0,3,6,9)
    ])
    def test_analytics_filters(self, api_client, admin_user, sample_licenses, filter_param, filter_value,
                               expected_count):
        """Test analytics filters work correctly"""
        api_client.force_authenticate(user=admin_user)

        # Test status filter
        if filter_param == 'status':
            response = api_client.get(f'/analytics/licenses/by-status?{filter_param}={filter_value}')
        elif filter_param == 'license_type':
            response = api_client.get(f'/analytics/licenses/by-type?{filter_param}={filter_value}')
        else:
            response = api_client.get(f'/reports/licenses/by-district?{filter_param}={filter_value}')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['total'] == expected_count

    def test_monthly_stats_structure(self, api_client, admin_user, sample_licenses):
        """Test monthly statistics return proper structure"""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get('/reports/licenses/monthly')

        assert response.status_code == status.HTTP_200_OK

        data = response.data['data']
        assert 'year' in data
        assert 'total' in data
        assert 'monthly_stats' in data
        assert len(data['monthly_stats']) == 12

        # Check each month has required fields
        for month_data in data['monthly_stats']:
            required_fields = ['month', 'month_name', 'applications', 'approved', 'rejected', 'pending']
            for field in required_fields:
                assert field in month_data

    def test_district_stats_aggregation(self, api_client, admin_user, sample_licenses):
        """Test district statistics properly aggregate data"""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get('/reports/licenses/by-district')

        assert response.status_code == status.HTTP_200_OK

        data = response.data['data']
        assert 'district_stats' in data
        assert len(data['district_stats']) > 0

        # Verify total applications match
        total_from_districts = sum(stat['applications'] for stat in data['district_stats'])
        assert total_from_districts == data['total']

    @pytest.mark.parametrize("endpoint,auth_required", [
        ('/api/analytics/licenses/by-status', True),
        ('/api/analytics/licenses/by-type', True),
        ('/api/reports/licenses/monthly', True),
        ('/api/reports/licenses/by-district', True),
        ('/api/reports/officers/performance', True),
    ])
    def test_analytics_authentication_required(self, api_client, endpoint, auth_required):
        """Test all analytics endpoints require authentication"""
        response = api_client.get(endpoint)

        if auth_required:
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
        else:
            assert response.status_code != status.HTTP_401_UNAUTHORIZED
class TestLicenseCountsByType(AnalyticsViewsTestCase):
    """Test cases for license_counts_by_type view"""

    def test_get_license_counts_by_type_success(self):
        """Test successful retrieval of license counts by type"""
        self.authenticate_admin()

        response = self