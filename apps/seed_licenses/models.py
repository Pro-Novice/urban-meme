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
    license_number   = models.CharField(max_length=100, db_index=True)   

    class Meta:
        ordering = ["-timestamp", "-block_number", "license_number"]

    def __str__(self):
        return f"{self.event_name} | {self.license_number} | tx:{self.transaction_hash}"
