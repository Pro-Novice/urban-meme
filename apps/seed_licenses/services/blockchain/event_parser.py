import logging
from typing import List, Dict, Tuple, Any
from datetime import datetime,timezone
from web3._utils.events import get_event_data
from django.db import transaction
from asgiref.sync import sync_to_async
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
    async def parse_and_store(self, receipt: Any) -> Tuple[int, List[Dict]]:
        """
        Decode all matching events from a transaction receipt and store them in DB.
        Returns: (license_id, decoded_events)
        """
        from types import SimpleNamespace

        license_id = None
        decoded_events = []

        try:
            # Normalize receipt
            if isinstance(receipt, SimpleNamespace):
                receipt = vars(receipt)
            elif not isinstance(receipt, dict):
                receipt = receipt.__dict__

            tx_hash = receipt.get("transactionHash")
            block_number = receipt.get("blockNumber")

            logger.info(f"[EVENT PARSER] Starting event decoding for tx={tx_hash}")
            logger.debug(f"[EVENT DEBUG] Raw receipt keys: {list(receipt.keys())}")
            logs = receipt.get("logs", [])
            logger.debug(f"[EVENT DEBUG] Logs count: {len(logs)}")

            if not logs:
                logger.warning(f"[EVENT PARSER] No logs found in receipt for tx={tx_hash}")
                return None, []

            for idx, log in enumerate(logs):
                try:
                    # Normalize each log to dict
                    if isinstance(log, SimpleNamespace):
                        log = vars(log)
                    elif not isinstance(log, dict):
                        log = log.__dict__

                    # Ensure topics and data are normalized
                    topics = []
                    for t in log.get("topics", []):
                        if hasattr(t, "hex"):
                            topics.append(t.hex())
                        elif isinstance(t, bytes):
                            topics.append(t.hex())
                        else:
                            topics.append(str(t))
                    data = log.get("data", "0x")

                    log_dict = {
                        "address": log.get("address"),
                        "data": data,
                        "topics": topics,
                        "logIndex": log.get("logIndex", 0),
                        "transactionIndex": log.get("transactionIndex", 0),
                        "transactionHash": tx_hash,
                        "blockNumber": block_number,
                        "blockHash": receipt.get("blockHash"),
                    }

                    if not log_dict["address"]:
                        logger.debug(f"[EVENT SKIP] Missing address at log {idx}")
                        continue

                    if log_dict["address"].lower() != self.contract_address.lower():
                        logger.debug(f"[EVENT SKIP] Log from {log_dict['address']} ≠ {self.contract_address}")
                        continue

                    for abi_event in [a for a in self.abi if a.get("type") == "event"]:
                        try:
                            # Match event topic
                            input_types = ",".join(i["type"] for i in abi_event["inputs"])
                            event_topic = w3.keccak(text=f"{abi_event['name']}({input_types})").hex().lower()

                            topic0 = topics[0].lower() if topics else None
                            if topic0 != event_topic:
                                continue

                            decoded = get_event_data(w3.codec, abi_event, log_dict)
                            event_name = abi_event["name"]
                            event_args = dict(decoded["args"])

                            # Transform timestamps + enums
                            timestamp_fields = [
                                "approvalDate", "expiryDate", "renewalDate",
                                "rejectionDate", "revokedDate", "applicationDate",
                                "verifiedDate", "detectedDate", "lastModifiedDate"
                            ]
                            for field in timestamp_fields:
                                if field in event_args and isinstance(event_args[field], (int, float)):
                                    event_args[field] = datetime.fromtimestamp(
                                        event_args[field], tz=timezone.utc
                                    ).strftime("%d %B %Y")

                            enum_transforms = {
                                "category": REVERSE_LICENSE_CATEGORY,
                                "oldStatus": LICENSE_STATUS_REVERSE,
                                "newStatus": LICENSE_STATUS_REVERSE,
                                "status": LICENSE_STATUS_REVERSE,
                                "changedByRole": REVERSE_OFFICER_ROLE
                            }
                            for field, mapping in enum_transforms.items():
                                if field in event_args:
                                    event_args[field] = mapping.get(event_args[field], event_args[field])

                            if "licenseId" in event_args:
                                license_id = event_args["licenseId"]

                            decoded_events.append({"event": event_name, **event_args})
                            await self._persist_event_async(receipt, event_name, event_args)

                            logger.info(f"[EVENT DECODED] ✅ {event_name} | license_id={license_id} | args={event_args}")
                            break
                        except Exception as e:
                            logger.debug(f"[EVENT FAIL] Failed to decode {abi_event.get('name')} event: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"[EVENT LOG ERROR] Skipping log {idx} due to {e}")
                    continue

        except Exception as e:
            logger.warning(f"[EVENT PARSER ERROR] {e}")

        logger.info(f"[EVENT PARSER COMPLETE] Parsed {len(decoded_events)} events for license_id={license_id}")
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

    async def _persist_event_async(self, receipt, event_name: str, event_args: Dict[str, Any]):
        """Async-safe event persistence using sync_to_async wrapper for Django ORM."""
        try:
            # ---------------- Normalize transaction hash ---------------- #
            tx_hash = None
            if isinstance(receipt, dict):
                tx_hash = receipt.get("transactionHash")
            else:
                tx_hash = getattr(receipt, "transactionHash", None)

            # Convert bytes / HexBytes → readable hex string
            if isinstance(tx_hash, (bytes, bytearray)):
                tx_hash = tx_hash.hex()
            elif hasattr(tx_hash, "hex"):
                tx_hash = tx_hash.hex()

            # Prefix with '0x' if missing
            if tx_hash and not str(tx_hash).startswith("0x"):
                tx_hash = f"0x{tx_hash}"

            # Truncate if it somehow exceeds DB length
            if tx_hash and len(tx_hash) > 66:
                logger.warning(f"[DB] Truncating long tx_hash ({len(tx_hash)} chars): {tx_hash}")
                tx_hash = tx_hash[:66]

            # ---------------- Normalize block number ---------------- #
            block_number = getattr(receipt, "blockNumber", None)
            if isinstance(receipt, dict):
                block_number = receipt.get("blockNumber", block_number)

            # ---------------- Extract license_id ---------------- #
            license_id = event_args.get("licenseId") or 0

            logger.info(
                f"[DB] Async saving event '{event_name}' "
                f"(license_id={license_id}, tx={tx_hash}, block={block_number})"
            )

            # ---------------- Async ORM persistence ---------------- #
            await sync_to_async(EventLog.objects.create)(
                event_name=event_name,
                license_id=license_id,
                block_number=block_number,
                transaction_hash=tx_hash,
                event_data=event_args,
            )

            logger.info(f"[DB] ✅ Persisted event '{event_name}' (license_id={license_id})")

        except Exception as e:
            logger.error(f"[DB ERROR] ❌ Failed to persist {event_name}: {e}", exc_info=True)
