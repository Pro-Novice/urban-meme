from django.db import models
from django.conf import settings

class License(models.Model):
    STATUS_CHOICES = [
        ("APPLIED", "Applied"),
        ("UNDER_REVIEW", "Under Review"),
        ("VERIFIED", "Verified"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("REVOKED", "Revoked"),
        ("EXPIRED", "Expired"),
    ]

    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    license_id = models.IntegerField(unique=True)  # from blockchain
    license_type = models.CharField(max_length=50)
    crop_type = models.CharField(max_length=50)
    seed_variety = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=255)
    quality_parameters = models.TextField()
    source = models.CharField(max_length=100)
    aadhaar = models.CharField(max_length=12)

    blockchain_tx_id = models.CharField(max_length=66)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="APPLIED")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"License {self.license_id} - {self.license_type}"

class BlockchainTransaction(models.Model):
    tx_hash = models.CharField(max_length=66, primary_key=True)
    block_number = models.IntegerField()
    status = models.CharField(max_length=10)
    timestamp = models.DateTimeField()
    action_type = models.CharField(max_length=50)
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='transactions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return f"TX {self.tx_hash[:10]}... for License {self.license.license_id}"
