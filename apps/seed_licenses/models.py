from django.db import models

class EventLog(models.Model):
    """
    Model to store smart contract events.
    """
    transaction_hash = models.CharField(max_length=66)
    block_number = models.IntegerField(db_index=True)
    # log_index = models.IntegerField()
    event_name = models.CharField(max_length=255, db_index=True)
    event_data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)
    license_id = models.IntegerField(db_index=True)
    


    def __str__(self):
        return f'{self.event_name} in tx: {self.transaction_hash}'

    class Meta:
        ordering = ['-timestamp', '-block_number', '-license_id']


class LicenseSubmission(models.Model):
    """
    Tracks submitted license numbers to enforce uniqueness at the API layer.
    """
    license_number = models.CharField(max_length=64, unique=True, db_index=True)
    license_id = models.IntegerField(null=True, blank=True, db_index=True)
    transaction_hash = models.CharField(max_length=66, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.license_number
