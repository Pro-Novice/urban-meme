from web3.exceptions import ContractLogicError
from .blockchain_services import get_contract, call_function, call_view_function, get_transaction_status
from Services.exceptions import BlockchainError
import logging
from .models import License, BlockchainTransaction
from django.utils.timezone import datetime
from web3 import Web3
logger = logging.getLogger(__name__)

class SeedLicenseHandler:
    def __init__(self):
        self.contract = get_contract("SeedLicenseTrackingSystem")

    def _call_function(self, function_name, *args, address=None, private_key=None):
        try:
            function = getattr(self.contract.functions, function_name)
            return call_function(function, *args, address=address, private_key=private_key)
        except ContractLogicError as e:
            raise BlockchainError(str(e))

    def _call_view_function(self, function_name, *args):
        try:
            function = getattr(self.contract.functions, function_name)
            return call_view_function(function, *args)
        except ContractLogicError as e:
            raise BlockchainError(str(e))

    def apply_for_license(self, farmer_data, address, private_key, user):
        receipt = self._call_function(
            'applyForLicense',
            farmer_data['name'],
            farmer_data['aadhaar'],
            farmer_data['location'],
            farmer_data['license_type'],
            farmer_data['seed_variety'],
            farmer_data['crop_type'],
            farmer_data['quantity'],
            farmer_data['quality_parameters'],
            farmer_data['source'],
            address=address,
            private_key=private_key
        )

        license_id = receipt.logs[0].args.licenseId

        # Save to DB
        License.objects.create(
            applicant=user,
            license_id=license_id,
            license_type=farmer_data['license_type'],
            crop_type=farmer_data['crop_type'],
            seed_variety=farmer_data['seed_variety'],
            quantity=farmer_data['quantity'],
            location=farmer_data['location'],
            quality_parameters=farmer_data['quality_parameters'],
            source=farmer_data['source'],
            aadhaar=farmer_data['aadhaar'],
            blockchain_tx_id=receipt.transactionHash.hex()
        )

        # Transaction log
        BlockchainTransaction.objects.create(
            tx_hash=receipt.transactionHash.hex(),
            block_number=receipt.blockNumber,
            status="CONFIRMED",
            timestamp=datetime.fromtimestamp(Web3().eth.get_block(receipt.blockNumber).timestamp),
            action_type="LICENSE_APPLY",
            license_id=license_id,
            created_by=user
        )

        return license_id, receipt

    def update_license_status(self, license_id, new_status, remarks, address, private_key, user, docs_hash=b''):
        receipt = self._call_function(
            'updateLicenseStatus',
            license_id,
            new_status,
            remarks,
            docs_hash,
            address=address,
            private_key=private_key
        )

        try:
            lic = License.objects.get(license_id=license_id)
            lic.status = self.map_status_enum_to_label(new_status)
            lic.updated_at = datetime.now()
            lic.save()

            BlockchainTransaction.objects.create(
                tx_hash=receipt.transactionHash.hex(),
                block_number=receipt.blockNumber,
                status="CONFIRMED",
                timestamp=datetime.fromtimestamp(Web3().eth.get_block(receipt.blockNumber).timestamp),
                action_type="STATUS_UPDATE",
                license=lic,
                created_by=user
            )

        except License.DoesNotExist:
            pass

        return receipt

    def map_status_enum_to_label(self, status_enum):
        mapping = {
            0: "APPLIED",
            1: "UNDER_REVIEW",
            2: "VERIFIED",
            3: "APPROVED",
            4: "REJECTED",
            5: "EXPIRED",
            6: "REVOKED"
        }
        return mapping.get(status_enum, "UNKNOWN")


    def revoke_license(self, license_id, reason, address, private_key=None):
        return self.update_license_status(license_id, 6, reason, address, private_key)

    def get_license_summary(self, license_id):
        return self._call_view_function('getLicenseSummary', license_id)

    def get_license_status(self, license_id):
        summary = self.get_license_summary(license_id)
        return summary['status']

    def get_license_history(self, license_id):
        count = self._call_view_function('getActionCount', license_id)
        history = []
        for i in range(count):
            action = self._call_view_function('getActionSummary', license_id, i)
            history.append({
                "timestamp": action[0],
                "department_officer": action[1],
                "officer_role": action[2],
                "previous_status": action[3],
                "new_status": action[4],
                "remarks": action[5]
            })
        return history

    def is_license_valid(self, license_id):
        return self._call_view_function('isLicenseValid', license_id)

    def generate_certificate_hash(self, license_id):
        return self._call_view_function('generateCertificateHash', license_id)

    def get_certificate_url(self, license_id):
        return f"https://rajkisan-dev.rajasthan.gov.in/certificates/{license_id}.pdf"

    def get_transaction_info(self, tx_hash):
        return get_transaction_status(tx_hash)
