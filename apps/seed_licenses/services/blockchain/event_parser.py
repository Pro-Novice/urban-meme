import logging
from typing import List, Dict, Tuple, Any
from datetime import datetime
from web3._utils.events import get_event_data
from django.db import transaction

from apps.seed_licenses.models import EventLog
from apps.seed_licenses.enums import (
    REVERSE_LICENSE_CATEGORY,
    LICENSE_STATUS_REVERSE,
    REVERSE_OFFICER_ROLE,
)
from .connection import w3
from .data_transformer import format_unix_timestamp

logger = logging.getLogger(__name__)

# ================== EVENT PARSING SERVICE ================== #
class EventParser:
    """
    Service class to decode and persist smart contract events.
    """

    def __init__(self, abi: List[Dict], contract_address: str):
        self.abi = abi
        self.contract_address = contract_address.lower()
        self.timestamp_fields = {
            "approvalDate", "expiryDate", "renewalDate",
            "rejectionDate", "revokedDate", "applicationDate",
            "verifiedDate", "detectedDate", "lastModifiedDate",
        }

        # Map of enum reversal for readability
        self.enum_transforms = {
            "category": REVERSE_LICENSE_CATEGORY,
            "oldStatus": LICENSE_STATUS_REVERSE,
            "newStatus": LICENSE_STATUS_REVERSE,
            "status": LICENSE_STATUS_REVERSE,
            "changedByRole": REVERSE_OFFICER_ROLE,
        }

    # ---------------- Decode and Persist ---------------- #
    def parse_and_store(self, receipt: Any) -> Tuple[int, List[Dict]]:
        """
        Decodes all matching events from a transaction receipt and stores them in DB.
        Returns: (license_id, decoded_events)
        """
        license_id = None
        decoded_events = []

        try:
            for log in receipt.logs:
                # Filter only logs emitted by this contract
                if log.address.lower() != self.contract_address:
                    continue

                # Try decoding this log with each ABI event definition
                for abi_event in [a for a in self.abi if a.get("type") == "event"]:
                    try:
                        if not self._matches_event(log, abi_event):
                            continue

                        decoded = get_event_data(w3.codec, abi_event, log)
                        event_name = abi_event["name"]
                        event_args = dict(decoded["args"])

                        # Apply field transformations
                        event_args = self._transform_event_fields(event_args)

                        # Capture license_id if present
                        if "licenseId" in event_args:
                            license_id = event_args["licenseId"]

                        # Append structured event
                        decoded_events.append({"event": event_name, **event_args})

                        # Persist event
                        self._persist_event(receipt, event_name, event_args)

                        break  # Move to next log once matched
                    except Exception as e:
                        logger.debug(f"Failed to decode {abi_event.get('name')} event: {e}")
                        continue

        except Exception as e:
            logger.warning(f"Event parsing failed: {e}")

        return license_id, decoded_events

    # ---------------- Internal Helpers ---------------- #
    def _matches_event(self, log, abi_event: Dict) -> bool:
        """Check if log corresponds to given ABI event signature."""
        try:
            input_types = ",".join(i["type"] for i in abi_event["inputs"])
            event_topic = w3.keccak(text=f"{abi_event['name']}({input_types})").hex()
            return log.topics[0].hex() == event_topic
        except Exception:
            return False

    def _transform_event_fields(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Applies timestamp and enum transformations."""
        transformed = {}

        for field, value in args.items():
            # Convert UNIX timestamps to readable strings
            if field in self.timestamp_fields and isinstance(value, int):
                transformed[field] = format_unix_timestamp(value)
                continue

            # Apply enum reversals for readability
            if field in self.enum_transforms:
                mapping = self.enum_transforms[field]
                transformed[field] = mapping.get(value, value)
                continue

            transformed[field] = value

        return transformed

    @transaction.atomic
    def _persist_event(self, receipt, event_name: str, event_args: Dict[str, Any]) -> None:
        """Save decoded event to EventLog table."""
        try:
            EventLog.objects.create(
                event_name=event_name,
                license_id=event_args.get("licenseId") or 0,
                block_number=receipt.blockNumber,
                transaction_hash=receipt.transactionHash.hex(),
                event_data=event_args,
            )
            logger.info(f"Saved event '{event_name}' (block {receipt.blockNumber})")
        except Exception as e:
            logger.error(f"Failed to persist event {event_name}: {e}")
