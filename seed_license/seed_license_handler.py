import logging
from datetime import datetime
from web3 import Web3
from web3.exceptions import ContractLogicError

from .blockchain_services import get_contract, call_function, call_view_function, get_transaction_status
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

    # ── internal wrappers ────────────────────────────────────────────
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

    # ── public helpers ───────────────────────────────────────────────
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
        
        print('==> Receipt logs:', receipt.logs[0])
        
        # Extract license ID from blockchain logs
        # The license ID is in topics[1] as hex, convert to integer
        if receipt.logs and len(receipt.logs[0].topics) > 1:
            license_id_hex = receipt.logs[0].topics[1]
            license_id = int(license_id_hex.hex(), 16)  # Convert hex to integer
            print(f'==> Extracted License ID: {license_id}')
        else:
            raise BlockchainError("No license ID found in blockchain response")

        lic = License.objects.create(
            applicant          = user,  # This can be None now
            license_id         = str(license_id),  # Use actual blockchain license ID
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

        BlockchainTransaction.objects.create(
            tx_hash      = receipt.transactionHash.hex(),
            block_number = receipt.blockNumber,
            status       = "CONFIRMED",
            timestamp    = datetime.now(),
            action_type  = "LICENSE_APPLY",
            license      = lic,
            created_by   = user,  # This can be None now
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

            BlockchainTransaction.objects.create(
                tx_hash      = receipt.transactionHash.hex(),
                block_number = receipt.blockNumber,
                status       = "CONFIRMED",
                timestamp    = datetime.fromtimestamp(Web3().eth.get_block(receipt.blockNumber).timestamp),
                action_type  = "STATUS_UPDATE",
                license      = lic,
                created_by   = user,  # This can be None now
            )
        except License.DoesNotExist:
            pass
        return receipt

    # ── read‑only helpers ────────────────────────────────────────────
    def get_license_summary(self, lid):
        return self._call_view("getLicenseSummary", lid)

    def get_license_status(self, lid):
        return self.get_license_summary(lid)["status"]

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