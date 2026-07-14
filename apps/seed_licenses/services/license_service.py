import logging
from typing import Dict, Any, List
from apps.seed_licenses.models import EventLog
from apps.seed_licenses.services.blockchain import TransactionService
from apps.seed_licenses.enums import (
    APPLICATION_LICENSE_TYPES,
    LICENSE_CATEGORY_MAP,
    LICENSE_STATUS_REVERSE,
    REVERSE_LICENSE_CATEGORY,
    LicenseStatusEnum,
)
from apps.seed_licenses.services.multi_account_manager import multi_account_manager
logger = logging.getLogger(__name__)


_EVENT_ACTION_TYPES = {
    "LICENSEAPPLICATIONSUBMITTED": "SUBMITTED",
    "LICENSEAPPLICATIONSUBMITTEDV2": "SUBMITTED",
    "LICENSEAPPROVED": "APPROVED",
    "LICENSEREJECTED": "REJECTED",
    "LICENSEREVOKED": "REVOKED",
    "LICENSERENEWED": "RENEWED",
    "LICENSEDETAILSUPDATED": "LICENSE_DETAILS_UPDATED",
}


def _normalize_event_name(value: Any) -> str:
    """Normalize Solidity event names without relying on their casing/style."""
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def _normalize_action_type(value: Any) -> str:
    """Normalize API/decoded enum values to the action-history representation."""
    if isinstance(value, int):
        value = LICENSE_STATUS_REVERSE.get(value, value)
    return str(value or "").strip().upper().replace(" ", "_").replace("-", "_")


def _event_matches_action(log: Dict[str, Any], action_type: Any) -> bool:
    """Return whether a persisted contract event represents an action-history row."""
    normalized_action = _normalize_action_type(action_type)
    event_name = _normalize_event_name(log.get("event_name"))

    direct_action = _EVENT_ACTION_TYPES.get(event_name)
    if direct_action is not None:
        return direct_action == normalized_action

    if event_name != "STATUSCHANGED":
        return False

    event_data = log.get("event_data") or {}
    return _normalize_action_type(event_data.get("newStatus")) == normalized_action


class ILicenseService:
    """Abstract service interface (for Dependency Inversion)."""

    def submit_application(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_basic_info(self, license_id: int) -> Dict[str, Any]: ...
    def update_status(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_action_history(self, license_id: int) -> List[Dict[str, Any]]: ...
    def verify_document(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def update_details(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_qr_data(self, license_id: int) -> Dict[str, Any]: ...
    def add_officer(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

class LicenseService(ILicenseService):
    """Business logic layer for license-related operations."""

    def __init__(self, tx_service: TransactionService):
        self.tx = tx_service

    # ---------- SUBMIT APPLICATION ---------- #
    def submit_application(self, data: Dict[str, Any]) -> Dict[str, Any]:
        category = data["license_category"]

        lat = data.get("latitude", 0)
        lng = data.get("longitude", 0)
        
        struct_input = {
            "category": data["license_category"],
            "applicationLicenseType": data["application_license_type"],
            "level": data["license_level"],
            "licenseNumber": data["license_number"],
            "registeringAuthority": data["registering_authority"],
            "registeringOfficeName": data["registering_office_name"],
            "applicantName": data["applicant_name"],
            "aadhaarNumber": data["aadhaar_number"],
            "applicantPermanentAddress": data["applicant_permanent_address"],
            "firmName": data["firm_name"],
            "firmType": data["firm_type"],
            "firmAddress": data["firm_address"],
            "salePointAddress": data["sale_point_address"],
            "saleStorageAddress": data["sale_storage_address"],
            "productionCompany": data["production_company"],
            "cropName": data["crop_name"],
            "cropVariety": data["crop_variety"],
            "latitude": int(lat),   
            "longitude": int(lng),   
        }
        return self.tx.write("submitLicenseApplicationV2", [struct_input])

    # ---------- GET BASIC INFO ---------- #
    def get_basic_info(self, license_id: int) -> Dict[str, Any]:
        return self.tx.read("getLicenseBasicInfo", [license_id])

    # ---------- UPDATE STATUS ---------- #
    def update_status(self, data: Dict[str, Any]) -> Dict[str, Any]:
        license_id = data["license_id"]

        current = self.tx.read("getLicenseBasicInfo", [license_id])
        current_enum = LicenseStatusEnum.from_string(current["status"])
        new_status = data["status"]

        # 1️ Idempotent same-status handling
        if new_status == current_enum:
            logger.info(
                "No-op: License %s already in status %s",
                license_id,
                LICENSE_STATUS_REVERSE[current_enum],
            )
            return {
                "license_id": license_id,
                "status": LICENSE_STATUS_REVERSE[current_enum],
                "changed": False,
                "message": f"License already in status {LICENSE_STATUS_REVERSE[current_enum]}",
            }

        # 2️ Validate allowed transitions
        allowed = data["valid_transitions"].get(current_enum, [])
        if new_status not in allowed:
            err_msg = (
                f"Invalid transition {LICENSE_STATUS_REVERSE[current_enum]} → "
                f"{LICENSE_STATUS_REVERSE[new_status]}"
            )
            logger.warning("License %s: %s", license_id, err_msg)
            raise ValueError(err_msg)

        # 3️ Apply status update via blockchain transaction
        logger.info(
            "Updating license %s: %s → %s by %s (%s)",
            license_id,
            LICENSE_STATUS_REVERSE[current_enum],
            LICENSE_STATUS_REVERSE[new_status],
            data["officer_name"],
            data["role"],
        )

        return self.tx.write(
            "updateLicenseStatus",
            [
                license_id,
                new_status,
                data["officer_name"],
                data["role"],
                data["remarks"],
                data.get("renewal_period_days", 0),
            ],
        )

    # ---------- HISTORY (ENRICHED) ---------- #
    def get_action_history(self, license_id: int) -> List[Dict[str, Any]]:
        """Fetch license action history and enrich with transaction hashes from EventLog."""
        try:
            # Read blockchain-stored action history
            actions = self.tx.read("getLicenseActionHistory", [license_id])
            if not actions:
                return []

            # Query local EventLog for blockchain transaction hashes
            # The model's default ordering is newest-first. Action history comes
            # from the contract oldest-first, so explicitly align the event logs
            # before matching them. ``id`` preserves receipt/log insertion order
            # when multiple events share a block and timestamp.
            unmatched_logs = list(
                EventLog.objects.filter(license_id=license_id)
                .values("transaction_hash", "event_name", "event_data")
                .order_by("block_number", "timestamp", "id")
            )

            enriched = []
            for action in actions:
                match = None
                for index, log in enumerate(unmatched_logs):
                    if _event_matches_action(log, action.get("actionType")):
                        # A blockchain event represents exactly one history action.
                        # Removing it prevents repeated actions (especially detail
                        # updates with identical remarks) from sharing a tx hash.
                        match = unmatched_logs.pop(index)
                        break

                enriched.append({
                    **action,
                    "transactionHash": match["transaction_hash"] if match else None,
                })

            return enriched

        except Exception as e:
            logger.exception("Failed to enrich action history for license %s", license_id)
            return self.tx.read("getLicenseActionHistory", [license_id])

    # ---------- VERIFY DOCUMENT ---------- #
    def verify_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.tx.write(
            "verifyLicenseWithHash",
            [data["license_number"], data["expected_hash"]],
        )

    # ---------- UPDATE DETAILS ---------- #
    def update_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        application_license_type = data.get("application_license_type")
        if application_license_type is not None:
            current_license = self.tx.read(
                "getLicenseBasicInfo",
                [data["license_id"]],
            )
            current_category = current_license.get("category")
            if isinstance(current_category, str):
                category = LICENSE_CATEGORY_MAP.get(current_category.strip().upper())
            else:
                category = current_category

            if category not in APPLICATION_LICENSE_TYPES:
                return {
                    "success": False,
                    "error": "Unable to determine the license category.",
                }

            allowed_types = APPLICATION_LICENSE_TYPES[category]
            if application_license_type not in allowed_types:
                category_name = REVERSE_LICENSE_CATEGORY[category]
                return {
                    "success": False,
                    "error": (
                        f"Invalid application license type for {category_name}. "
                        f"Allowed values: {', '.join(sorted(allowed_types))}."
                    ),
                }

        update_input = {
            "applicationLicenseType": application_license_type or "",
            "applicantName": data.get("applicant_name", ""),
            "aadhaarNumber": data.get("aadhaar_number", ""),
            "applicantPermanentAddress": data.get("applicant_permanent_address", ""),
            "firmName": data.get("firm_name", ""),
            "firmType": data.get("firm_type", ""),
            "firmAddress": data.get("firm_address", ""),
            "salePointAddress": data.get("sale_point_address", ""),
            "saleStorageAddress": data.get("sale_storage_address", ""),
            "productionCompany": data.get("production_company", ""),
            "cropName": data.get("crop_name", []),
            "cropVariety": data.get("crop_variety", ""),
            "isSeedSelfProduced": data.get("is_seed_self_produced", False),
            "isSeedSelfProducedProvided": "is_seed_self_produced" in data,
            "latitude": data.get("latitude", 0),
            "longitude": data.get("longitude", 0),
            "coordinatesProvided": "latitude" in data,
        }
        return self.tx.write(
            "updateLicenseDetails",
            [
                data["license_id"],
                update_input,
                data["role"],
            ],
        )

    # ---------- QR DATA ---------- #
    def get_qr_data(self, license_id: int) -> Dict[str, Any]:
        """Read-only blockchain call to fetch QR data for a given license."""
        return self.tx.read("getLicenseQRData", [license_id])
    
    # ---------- ADD OFFICER (ADMIN ONLY) ---------- #
    def add_officer(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new officer to authorized callers list.
        Only admin can perform this action.
        """
        caller_address = data["address"]
        new_officer_address = data["new_officer_address"]
        
        logger.info(
            "Adding new officer %s by admin %s",
            new_officer_address,
            caller_address
        )

        admin_account = multi_account_manager.get_account_by_address(caller_address)
        if not admin_account:
            return {
                "success": False,
                "error": f"No private key found for admin address {caller_address}"
            }

        return self.tx.write(
            "manageAuthorizedApiCallers",
            [new_officer_address, True],
            address=admin_account["address"],
            private_key=admin_account["private_key"]  
        )
