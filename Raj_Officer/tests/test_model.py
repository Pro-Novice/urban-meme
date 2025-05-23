"""
Unit tests for RajOfficer model and validators
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from Raj_Officer.models import RajOfficer
from Raj_Officer.models import (
    validate_designation, validate_department, validate_user_type,
    validate_gender, validate_user_id, validate_mobile_number,
    validate_aadhaar_number
)
from agri_backend.enums import Gender, Status, UserType
from Raj_Officer.enums import Designation, Department


class ValidatorsTestCase(TestCase):
    """Test cases for model validators"""

    def test_validate_designation_valid(self):
        """Test valid designation values"""
        for designation in Designation:
            try:
                validate_designation(designation.name)
            except ValidationError:
                self.fail(f"Valid designation {designation.name} raised ValidationError")

    def test_validate_designation_invalid(self):
        """Test invalid designation values"""
        with self.assertRaises(ValidationError):
            validate_designation("INVALID_DESIGNATION")

    def test_validate_department_valid(self):
        """Test valid department values"""
        for department in Department:
            try:
                validate_department(department.name)
            except ValidationError:
                self.fail(f"Valid department {department.name} raised ValidationError")

    def test_validate_department_invalid(self):
        """Test invalid department values"""
        with self.assertRaises(ValidationError):
            validate_department("INVALID_DEPARTMENT")

    def test_validate_user_type_valid(self):
        """Test valid user type values"""
        try:
            validate_user_type("USER")
            validate_user_type("RAJKISAN_OFFICER")
            validate_user_type("ADMIN")
            validate_user_type("FARMER")
            validate_user_type("user")  # lowercase should work
        except ValidationError:
            self.fail("Valid user type raised ValidationError")

    def test_validate_user_type_invalid(self):
        """Test invalid user type values"""
        with self.assertRaises(ValidationError):
            validate_user_type("INVALID_TYPE")

    def test_validate_gender_valid(self):
        """Test valid gender values"""
        try:
            validate_gender("MALE")
            validate_gender("FEMALE")
        except ValidationError:
            self.fail("Valid gender raised ValidationError")

    def test_validate_gender_invalid(self):
        """Test invalid gender values"""
        with self.assertRaises(ValidationError):
            validate_gender("male")  # lowercase not allowed
        with self.assertRaises(ValidationError):
            validate_gender("OTHER")

    def test_validate_user_id_valid(self):
        """Test valid user ID format"""
        try:
            validate_user_id("RAJKSNUSER12345")
        except ValidationError:
            self.fail("Valid user ID raised ValidationError")

    def test_validate_user_id_invalid(self):
        """Test invalid user ID formats"""
        invalid_ids = [
            "RAJKSNUSER1234",  # too short
            "RAJKSNUSER123456",  # too long
            "RAJKSNUSR12345",  # wrong prefix
            "RAJKSNUSER1234A",  # non-digit
        ]
        for invalid_id in invalid_ids:
            with self.assertRaises(ValidationError):
                validate_user_id(invalid_id)

    def test_validate_mobile_number_valid(self):
        """Test valid mobile number formats"""
        valid_numbers = ["9876543210", "8123456789", "7987654321", "6123456789"]
        for number in valid_numbers:
            try:
                validate_mobile_number(number)
            except ValidationError:
                self.fail(f"Valid mobile number {number} raised ValidationError")

    def test_validate_mobile_number_invalid(self):
        """Test invalid mobile number formats"""
        invalid_numbers = [
            "1234567890",  # doesn't start with 6-9
            "987654321",  # too short
            "98765432100",  # too long
            "987654321A",  # contains letter
        ]
        for number in invalid_numbers:
            with self.assertRaises(ValidationError):
                validate_mobile_number(number)

    def test_validate_aadhaar_number_valid(self):
        """Test valid Aadhaar number formats"""
        try:
            validate_aadhaar_number("123456789012")
        except ValidationError:
            self.fail("Valid Aadhaar number raised ValidationError")

    def test_validate_aadhaar_number_invalid(self):
        """Test invalid Aadhaar number formats"""
        invalid_numbers = [
            "012345678901",  # starts with 0
            "12345678901",  # too short
            "1234567890123",  # too long
            "12345678901A",  # contains letter
        ]
        for number in invalid_numbers:
            with self.assertRaises(ValidationError):
                validate_aadhaar_number(number)


class RajOfficerModelTestCase(TestCase):
    """Test cases for RajOfficer model"""

    def setUp(self):
        """Set up test data"""
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
            'role': 'FIELD_OFFICER'
        }

    def test_create_raj_officer_success(self):
        """Test successful creation of RajOfficer"""
        officer = RajOfficer.objects.create(**self.valid_officer_data)
        self.assertEqual(officer.user_id, 'RAJKSNOFSR12345')
        self.assertEqual(officer.name, 'Test Officer')
        self.assertEqual(officer.status, Status.PENDING.value)
        self.assertEqual(officer.user_type, UserType.RAJKISAN_OFFICER.value)

    def test_raj_officer_str_method(self):
        """Test string representation of RajOfficer"""
        officer = RajOfficer.objects.create(**self.valid_officer_data)
        expected_str = f"{officer.user_name} - {officer.department}"
        self.assertEqual(str(officer), expected_str)

    def test_raj_officer_unique_fields(self):
        """Test unique constraints on RajOfficer fields"""
        # Create first officer
        RajOfficer.objects.create(**self.valid_officer_data)

        # Try to create another with same mobile number
        duplicate_data = self.valid_officer_data.copy()
        duplicate_data['user_id'] = 'RAJKSNOFSR54321'
        duplicate_data['email'] = 'different@example.com'
        duplicate_data['aadhar_number'] = '987654321098'

        with self.assertRaises(IntegrityError):
            RajOfficer.objects.create(**duplicate_data)

    def test_raj_officer_invalid_user_id_format(self):
        """Test invalid user ID format in RajOfficer"""
        invalid_data = self.valid_officer_data.copy()
        invalid_data['user_id'] = 'INVALID_ID'

        officer = RajOfficer(**invalid_data)
        with self.assertRaises(ValidationError):
            officer.full_clean()

    def test_raj_officer_invalid_mobile_number(self):
        """Test invalid mobile number in RajOfficer"""
        invalid_data = self.valid_officer_data.copy()
        invalid_data['mobile_number'] = '1234567890'

        officer = RajOfficer(**invalid_data)
        with self.assertRaises(ValidationError):
            officer.full_clean()

    def test_raj_officer_invalid_aadhaar_number(self):
        """Test invalid Aadhaar number in RajOfficer"""
        invalid_data = self.valid_officer_data.copy()
        invalid_data['aadhar_number'] = '012345678901'

        officer = RajOfficer(**invalid_data)
        with self.assertRaises(ValidationError):
            officer.full_clean()

    def test_raj_officer_default_values(self):
        """Test default values in RajOfficer model"""
        minimal_data = {
            'user_id': 'RAJKSNOFSR12345',
            'designation': 'AGRICULTURE_OFFICER',
            'department': 'AGRICULTURE',
        }
        officer = RajOfficer.objects.create(**minimal_data)

        self.assertEqual(officer.name, '')
        self.assertEqual(officer.user_name, '')
        self.assertEqual(officer.mobile_number, '')
        self.assertEqual(officer.email, '')
        self.assertEqual(officer.address, '')
        self.assertEqual(officer.aadhar_number, '')
        self.assertEqual(officer.role, 'NONE')
        self.assertEqual(officer.wallet_address, '')
        self.assertEqual(officer.password_hash, '')
        self.assertFalse(officer.has_account)
        self.assertEqual(officer.status, Status.PENDING.value)
        self.assertEqual(officer.user_type, UserType.RAJKISAN_OFFICER.value)

    def test_raj_officer_meta_options(self):
        """Test model meta options"""
        self.assertEqual(RajOfficer._meta.verbose_name, 'Rajasthan Kisan Officer')
        self.assertEqual(RajOfficer._meta.verbose_name_plural, 'Rajasthan Kisan Officers')


@pytest.mark.django_db
class TestRajOfficerModelPytest:
    """Pytest version of RajOfficer model tests"""

    def test_officer_creation_with_fixture(self):
        """Test officer creation using pytest"""
        officer_data = {
            'user_id': 'RAJKSNOFSR99999',
            'name': 'Pytest Officer',
            'designation': 'AGRICULTURE_OFFICER',
            'department': 'AGRICULTURE',
        }
        officer = RajOfficer.objects.create(**officer_data)
        assert officer.user_id == 'RAJKSNOFSR99999'
        assert officer.name == 'Pytest Officer'

    def test_multiple_officers_creation(self):
        """Test creating multiple officers"""
        officers_data = [
            {
                'user_id': 'RAJKSNOFSR11111',
                'name': 'Officer 1',
                'mobile_number': '9111111111',
                'email': 'officer1@example.com',
                'aadhar_number': '111111111111',
                'designation': 'AGRICULTURE_OFFICER',
                'department': 'AGRICULTURE',
            },
            {
                'user_id': 'RAJKSNOFSR22222',
                'name': 'Officer 2',
                'mobile_number': '9222222222',
                'email': 'officer2@example.com',
                'aadhar_number': '222222222222',
                'designation': 'DISTRICT_COLLECTOR',
                'department': 'REVENUE',
            }
        ]

        officers = [RajOfficer.objects.create(**data) for data in officers_data]
        assert len(officers) == 2
        assert RajOfficer.objects.count() == 2