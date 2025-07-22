# models.py
from django.db import models

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