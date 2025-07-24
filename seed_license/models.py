from django.db import models


class BlockchainEvent(models.Model):
    """
    Model to store emitted events from the blockchain.
    This helps in querying, auditing, and tracking changes
    associated with specific transactions and licenses.
    """

    # Name of the event emitted from the smart contract (e.g., LicenseCreated, StatusUpdated)
    event_name = models.CharField(max_length=100)

    # ID of the license associated with the event, if any
    license_id = models.IntegerField(null=True, blank=True)

    # Block number on the blockchain in which the event was mined
    block_number = models.IntegerField()

    # Transaction hash (66 characters for 0x-prefixed Ethereum tx hash)
    tx_hash = models.CharField(max_length=66)

    # Smart contract address from which the event was emitted
    address = models.CharField(max_length=42)

    # Timestamp of when the event was stored in the database
    timestamp = models.DateTimeField(auto_now_add=True)

    # Full decoded event data payload in JSON format
    payload = models.JSONField()

    class Meta:
        verbose_name = 'Blockchain Event'
        verbose_name_plural = 'Blockchain Events'
        ordering = ['-timestamp']  # Latest events appear first

    def __str__(self):
        return f"{self.event_name} - Tx: {self.tx_hash[:10]}..."
