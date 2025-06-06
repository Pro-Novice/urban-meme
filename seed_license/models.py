from django.db import models
from django.conf import settings

class License(models.Model):
    STATUS_CHOICES = [
        ("APPLIED",                    "Applied"),
        ("DOCUMENTS_VERIFIED",        "Documents verified"),
        ("FIELD_INSPECTION_COMPLETED", "Field inspection completed"),
        ("QUALITY_VERIFIED",          "Quality verified"),
        ("APPROVED",                  "Approved"),
        ("REJECTED",                  "Rejected"),
        ("REVOKED",                   "Revoked"),
        ("EXPIRED",                   "Expired"),
    ]

    applicant          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    license_id         = models.IntegerField(unique=True)
    license_type       = models.CharField(max_length=50)
    crop_type          = models.CharField(max_length=50)
    seed_variety       = models.CharField(max_length=100)
    quantity           = models.DecimalField(max_digits=10, decimal_places=2)
    location           = models.CharField(max_length=255)
    quality_parameters = models.TextField()
    source             = models.CharField(max_length=100)
    aadhaar            = models.CharField(max_length=12)

    blockchain_tx_id   = models.CharField(max_length=66)
    status             = models.CharField(max_length=30, choices=STATUS_CHOICES, default="APPLIED")
    submitted_at       = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"License {self.license_id}"

class BlockchainTransaction(models.Model):
    tx_hash      = models.CharField(max_length=66, primary_key=True)
    block_number = models.IntegerField()
    status       = models.CharField(max_length=10)
    timestamp    = models.DateTimeField()
    action_type  = models.CharField(max_length=50)
    license      = models.ForeignKey(License, on_delete=models.CASCADE, related_name="transactions")
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"TX {self.tx_hash[:10]}… for License {self.license.license_id}"

class DocumentUploadLog(models.Model):
    dept_key = models.CharField(max_length=50)
    document_type = models.CharField(max_length=100)
    member_id = models.CharField(max_length=50, blank=True, null=True)
    enrollment_id = models.CharField(max_length=50, blank=True, null=True)
    certificate_id = models.CharField(max_length=50, blank=True, null=True)
    jan_aadhaar_id = models.CharField(max_length=50, blank=True, null=True)
    aadhaar_ref_no = models.CharField(max_length=50, blank=True, null=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    request_data = models.JSONField()
    response_data = models.JSONField()
    evault_doc_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20)
    message = models.TextField()
    incident_id = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    client_id_used = models.CharField(max_length=100, blank=True, null=True)
    is_update = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.document_type} - {self.status}"

    class Meta:
        verbose_name = "Document Upload Log"
        verbose_name_plural = "Document Upload Logs"