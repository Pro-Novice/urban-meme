from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator


class License(models.Model):
    STATUS_CHOICES = [
        ("APPLIED", "Applied"),
        ("DOCUMENTS_VERIFIED", "Documents verified"),
        ("FIELD_INSPECTION_COMPLETED", "Field inspection completed"),
        ("QUALITY_VERIFIED", "Quality verified"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("REVOKED", "Revoked"),
        ("EXPIRED", "Expired"),
    ]

    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    license_id = models.IntegerField(unique=True)
    license_type = models.CharField(max_length=50)
    crop_type = models.CharField(max_length=50)
    seed_variety = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    location = models.CharField(max_length=255)
    quality_parameters = models.TextField()
    source = models.CharField(max_length=100)
    aadhaar = models.CharField(max_length=12, validators=[RegexValidator(r'^\d{12}$')])

    blockchain_tx_id = models.CharField(max_length=66)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="APPLIED")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"License {self.license_id} ({self.get_status_display()})"


class BlockchainTransaction(models.Model):
    tx_hash = models.CharField(max_length=66, primary_key=True)
    block_number = models.IntegerField()
    status = models.CharField(max_length=10)
    timestamp = models.DateTimeField()
    action_type = models.CharField(max_length=50)
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name="transactions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"TX {self.tx_hash[:10]}… for License {self.license.license_id}"


class OfficerAction(models.Model):
    ACTION_TYPES = [
        ("DOC_VERIFICATION", "Document Verification"),
        ("FIELD_INSPECTION", "Field Inspection"),
        ("APPROVAL", "Approval"),
        ("REJECTION", "Rejection"),
        ("REVOKE", "Revoke"),
    ]

    officer_id = models.CharField(max_length=100)
    license = models.ForeignKey(License, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    tx_hash = models.CharField(max_length=66)