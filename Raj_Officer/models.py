import re
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# Third-party imports should be placed before first-party imports.
from agri_backend.enums import Gender, Status, UserType
from Raj_Officer.enums import Designation, Department

# Validators
def validate_designation(value):
    """
    Validate the designation value to ensure it's a valid member of the Designation Enum.
    """
    if value not in [e.name for e in Designation]:
        raise ValidationError("Invalid designation")

def validate_department(value):
    """
    Validate the department value to ensure it's a valid member of the Department Enum.
    """
    if value not in [e.name for e in Department]:
        raise ValidationError("Invalid department")

def validate_user_type(value):
    """
    Validate the user type value to ensure it's either  USER, FARMER, RAJKISAN_OFFICER, or ADMIN
    """
    if not UserType.__members__.get(value.upper()):
        raise ValidationError("Registration type must be USER, FARMER, RAJKISAN_OFFICER, or ADMIN ")

def validate_gender(value):
    """
    Validate the gender value to ensure it's either 'MALE' or 'FEMALE'.
    """
    if value not in ["MALE", "FEMALE"]:
        raise ValidationError("Gender must be MALE or FEMALE in capital letters")

def validate_user_id(value):
    """
    Validate the user ID format to ensure it follows the RAJKSNUSER[0-9]{5} format.
    """
    if not re.match(r"^RAJKSNUSER[0-9]{5}$", value):
        raise ValidationError("Not a valid user ID")

def validate_mobile_number(value):
    """
    Validate the mobile number to ensure it follows the correct format for Indian numbers.
    """
    if not re.match(r"^[6-9]{1}[0-9]{9}$", value):
        raise ValidationError("Not a valid mobile number")

def validate_aadhaar_number(value):
    """
    Validate the Aadhaar number format to ensure it follows the XXXXXXXXXXXX format.
    """
    if not re.match(r"^[1-9]{1}[0-9]{11}$", value):
        raise ValidationError("Not a valid Aadhaar number. Format: XXXXXXXXXXXX")

# Officer Role Model
class RajOfficer(models.Model):
    """
    Model representing a Rajasthan Officer. Includes personal details,
     department, role, blockchain fields, and other details.
    """
    user_id = models.CharField(
        primary_key=True,
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^RAJKSNOFSR[0-9]{5}$",
                message="Not a valid registration id"
            )
        ]
    )
    # Personal Details
    name = models.CharField(max_length=100, default='')
    user_name = models.CharField(max_length=100, default='')
    mobile_number = models.CharField(max_length=10, default='',
                                     validators=[validate_mobile_number], unique=True)
    email = models.CharField(max_length=100, default='', unique=True)
    address = models.CharField(max_length=100, default='')
    gender = models.CharField(max_length=10, choices=Gender.choices())
    aadhar_number = models.CharField(max_length=12, default='',
                                     validators=[validate_aadhaar_number], unique=True)
    designation = models.CharField(max_length=50, default="NONE",
                                   validators=[validate_designation])
    department = models.CharField(max_length=50, default="NONE",
                                  validators=[validate_department])
    role = models.CharField(max_length=50, default="NONE")

    # Blockchain fields
    has_account = models.BooleanField(default=False)
    wallet_address = models.CharField(max_length=100, default='')

    # Other details
    user_type = models.CharField(max_length=50, choices=UserType.choices(),
                                 default=UserType.RAJKISAN_OFFICER.value)
    status = models.CharField(max_length=50, choices=Status.choices(),
                              default=Status.PENDING.value)
    password_hash = models.CharField(max_length=100, default='')

    class Meta:
        verbose_name = 'Rajasthan Kisan Officer'
        verbose_name_plural = 'Rajasthan Kisan Officers'

    def __str__(self):
        """
        String representation of the RajOfficer model.
        """
        return f"{self.user_name} - {self.department}"
 # Corrected to self.user_id instead of self.userId
