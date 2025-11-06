import logging
from typing import Dict, Any, List
from apps.seed_licenses.models import EventLog
from apps.seed_licenses.services.blockchain import TransactionService
from apps.seed_licenses.enums import LicenseStatusEnum, LICENSE_STATUS_REVERSE

logger = logging.getLogger(__name__)


class ILicenseService:
    """Abstract service interface (for Dependency Inversion)."""

    def submit_application(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_basic_info(self, license_id: int) -> Dict[str, Any]: ...
    def update_status(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_action_history(self, license_id: int) -> List[Dict[str, Any]]: ...
    def verify_document(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def update_details(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_qr_data(self, license_id: int) -> Dict[str, Any]: ...


class LicenseService(ILicenseService):
    """Business logic layer for license-related operations."""

    def __init__(self, tx_service: TransactionService):
        self.tx = tx_service

    # ---------- SUBMIT APPLICATION ---------- #
    def submit_application(self, data: Dict[str, Any]) -> Dict[str, Any]:
        struct_input = {
            "category": data["license_category"],
            "level": data["license_level"],
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
        }
        return self.tx.write("submitLicenseApplication", [struct_input])

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
            logs = EventLog.objects.filter(
                license_id=license_id
            ).values("transaction_hash", "event_name", "event_data")

            enriched = []
            for action in actions:
                # Try to match event by status keyword or remarks content
                match = next(
                    (
                        log for log in logs
                        if log["event_name"].upper().find(action["actionType"]) != -1
                        or log["event_data"].get("remarks") == action.get("remarks")
                    ),
                    None,
                )

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
        return self.tx.write(
            "updateLicenseDetails",
            [
                data["license_id"],
                data.get("firm_name", ""),
                data.get("firm_type", ""),
                data.get("firm_address", ""),
                data.get("sale_point_address", ""),
                data.get("sale_storage_address", ""),
                data.get("production_company", ""),
                data.get("crop_name", ""),
                data.get("crop_variety", ""),
                data["role"],
            ],
        )

    # ---------- QR DATA ---------- #
    def get_qr_data(self, license_id: int) -> Dict[str, Any]:
        """Read-only blockchain call to fetch QR data for a given license."""
        return self.tx.read("getLicenseQRData", [license_id])
