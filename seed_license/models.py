# models.py
from django.db import models
import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email


def validate_email(value):
    """email format validation"""
    try:
        django_validate_email(value)
    except ValidationError:
        raise ValidationError("Invalid email address")


def validate_pincode(value):
    if not re.match(r"^[1-9][0-9]{5}$", str(value)):
        raise ValidationError("Pincode must be 6 digits (no leading zero)")


def validate_aadhaar(value):
    if not re.match(r"^[1-9][0-9]{11}$", value):
        raise ValidationError("Aadhaar must be 12 digits (no leading zero)")


def validate_mobile(value):
    if not re.match(r"^(\+91[\-\s]?)?[6-9]\d{9}$", value):
        raise ValidationError("Invalid phone number")


def validate_username(value):
    if not re.match(r"^[\w.@+-]+$", value):
        raise ValidationError("Username may contain only letters, digits and @/./+/-/_")


def validate_name(value):
    if not re.match(r"^[a-zA-Z \-'.]{2,100}$", value):
        raise ValidationError("Name must be 2-100 characters with valid characters")


def validate_password(value):
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", value):
        raise ValidationError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValidationError("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", value):
        raise ValidationError("Password must contain at least one digit")


def validate_address(value):
    if not isinstance(value, dict):
        raise ValidationError("Address must be a dictionary")
    required_fields = ['address', 'city', 'state', 'postal_code', 'country']
    missing = [field for field in required_fields if field not in value]
    if missing:
        raise ValidationError(f"Missing address fields: {', '.join(missing)}")
    validate_pincode(value['postal_code'])


class BlockchainEvent(models.Model):
    event_name = models.CharField(max_length=100)
    license_id = models.IntegerField(null=True, blank=True)
    block_number = models.IntegerField()
    tx_hash = models.CharField(max_length=66)
    address = models.CharField(max_length=42)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()
    class Meta:
        verbose_name = 'Blockchain Event'
        verbose_name_plural = 'Blockchain Events'
        ordering = ['-timestamp']