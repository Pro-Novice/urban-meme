import logging
from datetime import datetime, timezone
from typing import Any, Dict

from apps.seed_licenses.enums import (
    LICENSE_CATEGORIES,
    LICENSE_CATEGORY_MAP,
    LICENSE_LEVELS,
    LICENSE_STATUSES,
    LICENSE_ACTION_TYPES,
    USER_ROLE,
)

logger = logging.getLogger(__name__)

# ================== TRANSFORMATION CONFIGURATION ================== #
GENERIC_TRANSFORM_MAP = {
    "getLicenseBasicInfo": {
        "fields": [
            "licenseId", "licenseNumber", "applicantName", "category", "level", "status",
            "firmName", "firmType", "firmAddress", "salePointAddress", "saleStorageAddress",
            "productionCompany", "cropName", "cropVariety", "registeringOfficeName",
            "registeringAuthority", "applicationDate", "approvalDate", "rejectionDate",
            "expiryDate", "revokedDate", "renewalDate", "latitude", "longitude", "isActive",
            "isPaid", "documentsVerified", "inspectionPassed", "applicationLicenseType"
            
        ],
        "enum_mappings": {
            "category": LICENSE_CATEGORIES,
            "level": LICENSE_LEVELS,
            "status": LICENSE_STATUSES
        },
        "timestamp_fields": [
            "applicationDate", "approvalDate", "rejectionDate",
            "expiryDate", "revokedDate", "renewalDate"
        ],
    },
    "getLicenseActionHistory": {
        "fields": ["timestamp", "actionType", "actorName", "actorRole", "remarks", "dataHash"],
        "enum_mappings": {
            "actionType": LICENSE_ACTION_TYPES,
            "actorRole": USER_ROLE
        },
        "timestamp_fields": ["timestamp"]
    },
    "getLicenseQRData": {
        "fields": ["verificationHash", "licenseNumber"],
        "enum_mappings": {},
        "timestamp_fields": []
    }
}

# ================== UTILITY FUNCTIONS ================== #
def format_unix_timestamp(ts: int) -> str:
    """Convert unix timestamp (int) into human-readable UTC date string."""
    if not ts or ts == 0:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %B %Y")
    except Exception as e:
        logger.warning(f"Timestamp conversion failed for {ts}: {e}")
        return None


# ================== CORE TRANSFORMATION LOGIC ================== #
def generic_transform(method_name: str, raw_data: Any) -> Any:
    """
    Applies generic field mapping, enum conversion, and timestamp formatting
    to smart contract tuple or list responses.
    """
    config = GENERIC_TRANSFORM_MAP.get(method_name)
    if not config:
        return raw_data

    fields = config["fields"]
    enum_mappings = config.get("enum_mappings", {})
    timestamp_fields = set(config.get("timestamp_fields", []))

    # Handle list of tuples (multiple records)
    if isinstance(raw_data, (list, tuple)) and all(isinstance(item, (list, tuple)) for item in raw_data):
        return [generic_transform(method_name, item) for item in raw_data]

    transformed = {}
    status_str = None

    for i, field in enumerate(fields):
        # Extract field value from tuple or dict
        if isinstance(raw_data, dict):
            value = raw_data.get(field)
        elif isinstance(raw_data, (list, tuple)) and i < len(raw_data):
            value = raw_data[i]
        else:
            value = None

        # Enum conversion
        if field in enum_mappings:
            enum_list = enum_mappings[field]
            if isinstance(value, int) and value < len(enum_list):
                transformed[field] = enum_list[value]
            else:
                transformed[field] = "UNKNOWN"
            if field == "status":
                status_str = transformed[field]

        # Timestamp formatting
        elif field in timestamp_fields and value:
            transformed[field] = format_unix_timestamp(value)
        
        elif field in {"latitude", "longitude"}:
            if value is not None:
                transformed[field] = float(value) / 1_000_000
            else:
                transformed[field] = None

        else:
            transformed[field] = value


    # Cleanup irrelevant date fields based on license status
    _cleanup_dates(transformed, status_str)
    if transformed.get("category") == "SEED":
        transformed.pop("latitude", None)
        transformed.pop("longitude", None)
    return transformed


def _cleanup_dates(data: Dict[str, Any], status_str: str) -> None:
    """Remove non-applicable date fields depending on license status."""
    if not status_str:
        return

    status_cleanup = {
        "APPROVED": ["rejectionDate", "revokedDate", "renewalDate"],
        "REJECTED": ["approvalDate", "expiryDate", "revokedDate", "renewalDate"],
        "REVOKED": ["approvalDate", "rejectionDate", "expiryDate", "renewalDate"],
        "EXPIRED": ["approvalDate", "rejectionDate", "revokedDate"],
        "RENEWED": ["rejectionDate", "revokedDate"]
    }

    extra_cleanup_statuses = {
        "SUBMITTED", "UNDER_REVIEW", "DOCUMENTS_VERIFIED",
        "INSPECTION_SCHEDULED", "INSPECTION_COMPLETED"
    }

    all_fields_to_pop = [
        "approvalDate", "rejectionDate", "expiryDate", "renewalDate", "revokedDate"
    ]

    if status_str in status_cleanup:
        for f in status_cleanup[status_str]:
            data.pop(f, None)

    if status_str in extra_cleanup_statuses:
        for f in all_fields_to_pop:
            data.pop(f, None)


def format_and_transform_response(result: Any, method_name: str, contract: Any) -> Any:
    """
    Entry point: takes raw contract output and returns a structured, readable dict.
    """
    config = GENERIC_TRANSFORM_MAP.get(method_name)
    if not config:
        return result

    # Handle single-field outputs
    if not isinstance(result, (list, tuple, dict)) and len(config.get("fields", [])) == 1:
        result = (result,)

    return generic_transform(method_name, result)
