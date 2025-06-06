from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Document(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents", null=True)
    file = models.FileField(upload_to='documents/')
    filename = models.CharField(max_length=255)
    sha256_hash = models.CharField(max_length=64, unique=True)  # SHA-256 is 64 chars hex
    # blockchain_doc_id = models.PositiveBigIntegerField()
    # blockchain_tx_id = models.CharField(max_length=66)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id} - {self.filename}"