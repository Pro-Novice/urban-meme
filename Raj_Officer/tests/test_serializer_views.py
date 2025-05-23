"""
Unit tests for RajOfficer serializers
"""
import pytest
from django.test import TestCase
from unittest.mock import Mock, patch
from Raj_Officer.serializer import RajasthanOfficerSerializer
from Raj_Officer.models import RajOfficer
from agri_backend.enums import Gender


class RajasthanOfficerSerializerTestCase(TestCase):
    """Test cases for RajasthanOfficerSerializer"""

    def setUp(self):
        """Set up test data"""
        self.valid_data = {
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

    def test_serializer_valid_data(self):
        """Test serializer with valid data"""
        serializer = RajasthanOfficerSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(len(serializer.errors), 0)

    def test_serializer_missing_required_fields(self):
        """Test serializer with missing required fields"""
        required_fields = ['user_id', 'name', 'password', 'confirm_password']

        for field in required_fields:
            data = self.valid_data.copy()
            del data[field]

            serializer = RajasthanOfficerSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)

    def test_serializer_password_mismatch(self):
        """Test serializer with mismatched passwords"""
        data = self.valid_data.copy()
        data['confirm_password'] = 'differentpassword'

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)
        self.assertEqual(
            serializer.errors['password'][0],
            "Passwords do not match"
        )

    def test_serializer_invalid_user_id_format(self):
        """Test serializer with invalid user ID format"""
        data = self.valid_data.copy()
        data['user_id'] = 'INVALID_FORMAT'

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('user_id', serializer.errors)

    def test_serializer_invalid_mobile_number(self):
        """Test serializer with invalid mobile number"""
        data = self.valid_data.copy()
        data['mobile_number'] = '1234567890'  # Invalid format

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('mobile_number', serializer.errors)

    def test_serializer_invalid_aadhaar_number(self):
        """Test serializer with invalid Aadhaar number"""
        data = self.valid_data.copy()
        data['aadhar_number'] = '012345678901'  # Starts with 0

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('aadhar_number', serializer.errors)

    def test_serializer_invalid_email_format(self):
        """Test serializer with invalid email format"""
        data = self.valid_data.copy()
        data['email'] = 'invalid-email-format'

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_serializer_invalid_designation(self):
        """Test serializer with invalid designation"""
        data = self.valid_data.copy()
        data['designation'] = 'INVALID_DESIGNATION'

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('designation', serializer.errors)

    def test_serializer_invalid_department(self):
        """Test serializer with invalid department"""
        data = self.valid_data.copy()
        data['department'] = 'INVALID_DEPARTMENT'

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('department', serializer.errors)

    def test_serializer_invalid_gender(self):
        """Test serializer with invalid gender"""
        data = self.valid_data.copy()
        data['gender'] = 'INVALID_GENDER'

        serializer = RajasthanOfficerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('gender', serializer.errors)

    @patch('Raj_Officer.serializer.RSAEncryption')
    def test_serializer_create_success(self, mock_rsa):
        """Test successful creation through serializer"""
        # Mock RSAEncryption
        mock_crypto = Mock()
        mock_crypto.hash_data.return_value = 'hashed_password'
        mock_rsa.return_value = mock_crypto

        serializer = RajasthanOfficerSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

        officer = serializer.save()

        self.assertIsInstance(officer, RajOfficer)
        self.assertEqual(officer.user_id, 'RAJKSNOFSR12345')
        self.assertEqual(officer.name, 'Test Officer')
        self.assertEqual(officer.password_hash, 'hashed_password')

        # Verify password hashing was called
        mock_crypto.hash_data.assert_called_once_with('testpassword123')

    @patch('Raj_Officer.serializer.RSAEncryption')
    def test_serializer_create_removes_confirm_password(self, mock_rsa):
        """Test that confirm_password is removed during creation"""
        mock_crypto = Mock()
        mock_crypto.hash_data.return_value = 'hashed_password'
        mock_rsa.return_value = mock_crypto

        serializer = RajasthanOfficerSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

        officer = serializer.save()

        # Verify officer was created without confirm_password field
        self.assertIsInstance(officer, RajOfficer)
        self.assertFalse(hasattr(officer, 'confirm_password'))

    def test_serializer_write_only_fields(self):
        """Test that password fields are write-only"""
        serializer = RajasthanOfficerSerializer()

        # Check that password and confirm_password are write-only
        password_field = serializer.fields['password']
        confirm_password_field = serializer.fields['confirm_password']

        self.assertTrue(password_field.write_only)
        self.assertTrue(confirm_password_field.write_only)

    def test_serializer_field_inclusion(self):
        """Test that all required fields are included in serializer"""
        expected_fields = {
            'user_id', 'name', 'user_name', 'mobile_number', 'email',
            'address', 'gender', 'aadhar_number', 'designation',
            'department', 'role', 'password', 'confirm_password'
        }

        serializer = RajasthanOfficerSerializer()
        serializer_fields = set(serializer.fields.keys())

        self.assertEqual(serializer_fields, expected_fields)

    def test_serializer_with_existing_officer(self):
        """Test serializer with existing officer data"""
        # Create an officer first
        officer = RajOfficer.objects.create(
            user_id='RAJKSNOFSR12345',
            name='Test Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE'
        )

        serializer = RajasthanOfficerSerializer(officer)
        data = serializer.data

        self.assertEqual(data['user_id'], 'RAJKSNOFSR12345')
        self.assertEqual(data['name'], 'Test Officer')
        self.assertNotIn('password', data)  # Password should not be serialized
        self.assertNotIn('confirm_password', data)

    def test_serializer_partial_update(self):
        """Test serializer with partial data for updates"""
        # Create an officer first
        officer = RajOfficer.objects.create(
            user_id='RAJKSNOFSR12345',
            name='Test Officer',
            designation='AGRICULTURE_OFFICER',
            department='AGRICULTURE'
        )

        # Update with partial data
        update_data = {'name': 'Updated Officer Name'}
        serializer = RajasthanOfficerSerializer(officer, data=update_data, partial=True)

        self.assertTrue(serializer.is_valid())
        updated_officer = serializer.save()
        self.assertEqual(updated_officer.name, 'Updated Officer Name')


@pytest.mark.django_db
class TestRajasthanOfficerSerializerPytest:
    """Pytest version of serializer tests"""

    @pytest.fixture
    def valid_officer_data(self):
        """Fixture for valid officer data"""
        return {
            'user_id': 'RAJKSNOFSR99999',
            'name': 'Pytest Officer',
            'user_name': 'pytestofficer',
            'mobile_number': '9999999999',
            'email': 'pytest@example.com',
            'address': 'Pytest Address',
            'gender': Gender.FEMALE.value,
            'aadhar_number': '999999999999',
            'designation': 'DISTRICT_COLLECTOR',
            'department': 'REVENUE',
            'role': 'ADMIN',
            'password': 'pytestpassword123',
            'confirm_password': 'pytestpassword123'
        }

    def test_serializer_validation_with_pytest(self, valid_officer_data):
        """Test serializer validation using pytest"""
        serializer = RajasthanOfficerSerializer(data=valid_officer_data)
        assert serializer.is_valid()
        assert len(serializer.errors) == 0

    @pytest.mark.parametrize("field", [
        'user_id', 'name', 'password', 'confirm_password'
    ])
    def test_required_fields_missing(self, valid_officer_data, field):
        """Test missing required fields using parametrize"""
        data = valid_officer_data.copy()
        del data[field]

        serializer = RajasthanOfficerSerializer(data=data)
        assert not serializer.is_valid()
        assert field in serializer.errors

    @pytest.mark.parametrize("password,confirm_password,should_be_valid", [
        ('password123', 'password123', True),
        ('password123', 'different123', False),
        ('', '', False),  # Empty passwords
    ])
    def test_password_validation(self, valid_officer_data, password, confirm_password, should_be_valid):
        """Test password validation scenarios"""
        data = valid_officer_data.copy()
        data['password'] = password
        data['confirm_password'] = confirm_password

        serializer = RajasthanOfficerSerializer(data=data)
        assert serializer.is_valid() == should_be_valid

        if not should_be_valid and password != confirm_password and password and confirm_password:
            assert 'password' in serializer.errors