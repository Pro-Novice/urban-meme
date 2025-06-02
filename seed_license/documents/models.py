from django.conf import settings
from django.db import models

class Document(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents"
    )
    file = models.FileField(upload_to="documents/%Y/%m/%d/")
    filename = models.CharField(max_length=255)
    sha256_hash = models.CharField(max_length=64, db_index=True)
    blockchain_doc_id = models.PositiveBigIntegerField()
    blockchain_tx_id = models.CharField(max_length=66)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id} – {self.filename}"
