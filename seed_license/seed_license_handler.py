import logging
from datetime import datetime
from django.utils.timezone import make_aware
from web3.exceptions import ContractLogicError
from .blockchain_services import get_contract, call_function, call_view_function, get_transaction_status, w3
from Services.exceptions import BlockchainError
from .models import License, BlockchainTransaction
logger = logging.getLogger(__name__)


class SeedLicenseHandler:
    def __init__(self):
        self.contract = get_contract("SeedLicenseTrackingSystem")

    LICENSE_TYPE_MAPPING = {
        "SEED_PRODUCTION":        0,
        "SEED_DISTRIBUTION":      1,
        "SEED_CERTIFICATION":     2,
        "HYBRID_SEED_PRODUCTION": 3,
        "ORGANIC_SEED_PRODUCTION":4,
    }

    STATUS_LABELS = {
        0: "APPLIED",
        1: "DOCUMENTS_VERIFIED",
        2: "FIELD_INSPECTION_COMPLETED",
        3: "QUALITY_VERIFIED",
        4: "APPROVED",
        5: "REJECTED",
        6: "REVOKED",
        7: "EXPIRED",
    }


    def _call_function(self, fname, *args):
        try:
            fn = getattr(self.contract.functions, fname)
            return call_function(fn, *args)
        except ContractLogicError as exc:
            raise BlockchainError(str(exc))

    def _call_view(self, fname, *args):
        try:
            fn = getattr(self.contract.functions, fname)
            return call_view_function(fn, *args)
        except ContractLogicError as exc:
            raise BlockchainError(str(exc))


    def apply_for_license(self, data: dict, user=None):
        ltype_str  = data["license_type"].upper()
        ltype_enum = self.LICENSE_TYPE_MAPPING.get(ltype_str)
        if ltype_enum is None:
            raise BlockchainError(f"Invalid license_type: {ltype_str}")

        receipt = self._call_function(
            "applyForLicense",
            data["name"],
            data["aadhaar"],
            data["location"],
            ltype_enum,
            data["seed_variety"],
            data["crop_type"],
            int(data["quantity"]),
            data["quality_parameters"],
            data["source"],
        )

        event_logs = []

        for log in receipt["logs"]:
            if log["address"].lower() == self.contract.address.lower():
                try:
                    decoded = self.contract.events.LicenseApplied().process_log(log)
                    event_logs.append(decoded)
                except Exception:
                    continue

        if not event_logs:
            raise BlockchainError("License application failed - no LicenseApplied event found")

        license_id = event_logs[0]["args"]["licenseId"]

        lic = License.objects.create(
            applicant          = user,
            license_id         = license_id,
            license_type       = ltype_str,
            crop_type          = data["crop_type"],
            seed_variety       = data["seed_variety"],
            quantity           = data["quantity"],
            location           = data["location"],
            quality_parameters = data["quality_parameters"],
            source             = data["source"],
            aadhaar            = data["aadhaar"],
            blockchain_tx_id   = receipt.transactionHash.hex(),
        )
        block = w3.eth.get_block(receipt.blockNumber)
        BlockchainTransaction.objects.create(
            tx_hash      = receipt.transactionHash.hex(),
            block_number = receipt.blockNumber,
            status       = "CONFIRMED",
            timestamp    = make_aware(datetime.fromtimestamp(block.timestamp)),
            action_type  = "LICENSE_APPLY",
            license      = lic,
            created_by   = user,
        )
        return license_id, receipt

    def update_license_status(self, license_id: int, new_status: int, remarks: str, user=None, docs_hash=b""):
        receipt = self._call_function(
            "updateLicenseStatus",
            license_id,
            new_status,
            remarks,
            docs_hash,
        )

        try:
            lic = License.objects.get(license_id=license_id)
            lic.status     = self.STATUS_LABELS.get(new_status, "UNKNOWN")
            lic.updated_at = datetime.now()
            lic.save()
            block = w3.eth.get_block(receipt.blockNumber)

            BlockchainTransaction.objects.create(
                tx_hash      = receipt.transactionHash.hex(),
                block_number = receipt.blockNumber,
                status       = "CONFIRMED",
                timestamp    = make_aware(datetime.fromtimestamp(block.timestamp)),
                action_type  = "STATUS_UPDATE",
                license      = lic,
                created_by   = user,
            )
        except License.DoesNotExist:
            pass
        return receipt


    def get_license_summary(self, lid):
        return self._call_view("getLicenseSummary", lid)

    def get_license_status(self, lid):
        return self._call_view("getLicenseSummary", lid)[9]

    def get_license_history(self, lid):
        count = self._call_view("getActionCount", lid)
        history = []
        for i in range(count):
            ts, officer, role, prev_s, new_s, remarks = self._call_view("getActionSummary", lid, i)
            history.append({
                "timestamp": ts,
                "department_officer": officer,
                "officer_role": role,
                "previous_status": prev_s,
                "new_status": new_s,
                "remarks": remarks,
            })
        return history

    def is_license_valid(self, lid):
        return self._call_view("isLicenseValid", lid)

    def get_certificate_url(self, lid):
        return f"https://rajkisan-dev.rajasthan.gov.in/certificates/{lid}.pdf"

    def get_transaction_info(self, tx_hash):
        return get_transaction_status(tx_hash)