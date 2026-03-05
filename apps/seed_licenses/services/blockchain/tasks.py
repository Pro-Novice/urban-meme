# apps/seed_licenses/services/blockchain/tasks.py
from celery import shared_task
from .connection import w3
from .event_parser import EventParser
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_transaction_confirmation(tx_hash: str, abi, contract_address: str):
    """Waits for transaction confirmation, decodes events, and saves them."""
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        parser = EventParser(abi, contract_address)
        license_id, events = parser.parse_and_store(receipt)
        logger.info(f"Transaction {tx_hash} confirmed: {len(events)} events parsed")
    except Exception as e:
        logger.error(f"Error processing transaction {tx_hash}: {e}")
