import logging
from datetime import datetime
from web3 import Web3
from web3.exceptions import ContractLogicError
from django.conf import settings

from Services.exceptions import BlockchainError
from ..blockchain_services import get_contract, call_function, call_view_function

logger = logging.getLogger(__name__)

class BlockchainAPIService:
    """
    Service class for handling blockchain API operations using the smart contract
    """
    def __init__(self):
        self.contract = get_contract("SeedLicenseTrackingSystem")
        self.w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL))
        
    # License type and status mapping
    LICENSE_TYPES = {
        0: "SEED_PRODUCTION",
        1: "SEED_DISTRIBUTION",
        2: "SEED_CERTIFICATION",
        3: "HYBRID_SEED_PRODUCTION",
        4: "ORGANIC_SEED_PRODUCTION"
    }
    
    DEPARTMENT_ROLES = {
        0: "AGRICULTURE_OFFICER",
        1: "DISTRICT_COLLECTOR",
        2: "SEED_CERTIFICATION_OFFICER",
        3: "SUBSIDY_APPROVAL_OFFICER",
        4: "QUALITY_CONTROL_OFFICER"
    }
    
    LICENSE_STATUS = {
        0: "APPLIED",
        1: "DOCUMENTS_VERIFIED",
        2: "FIELD_INSPECTION_COMPLETED",
        3: "QUALITY_VERIFIED",
        4: "APPROVED",
        5: "REJECTED",
        6: "REVOKED",
        7: "EXPIRED"
    }
    
    def _call_contract_function(self, function_name, *args):
        """Helper method to call a contract function and handle errors"""
        try:
            fn = getattr(self.contract.functions, function_name)
            return call_function(fn, *args)
        except ContractLogicError as exc:
            logger.error(f"Contract error on {function_name}: {exc}")
            raise BlockchainError(str(exc))
        except Exception as exc:
            logger.exception(f"Error calling {function_name}")
            raise
            
    def _call_contract_view(self, function_name, *args):
        """Helper method to call a contract view function and handle errors"""
        try:
            fn = getattr(self.contract.functions, function_name)
            return call_view_function(fn, *args)
        except ContractLogicError as exc:
            logger.error(f"Contract view error on {function_name}: {exc}")
            raise BlockchainError(str(exc))
        except Exception as exc:
            logger.exception(f"Error calling view {function_name}")
            raise
    
    # Admin operations
    def get_admin(self):
        """Get the current admin address"""
        return self._call_contract_view("admin")
    
    def change_admin(self, new_admin_address):
        """Change the admin address"""
        if not Web3.is_address(new_admin_address):
            raise BlockchainError("Invalid Ethereum address format")
        
        receipt = self._call_contract_function("changeAdmin", new_admin_address)
        return {
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "new_admin_address": new_admin_address
        }
    
    # Officer management
    def add_department_officer(self, officer_address, role_id):
        """Add a department officer with the specified role"""
        if not Web3.is_address(officer_address):
            raise BlockchainError("Invalid Ethereum address format")
        
        if not isinstance(role_id, int) or not (0 <= role_id <= 4):
            raise BlockchainError("Invalid role_id. Must be integer between 0-4")
        
        receipt = self._call_contract_function("addDepartmentOfficer", officer_address, role_id)
        return {
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "officer_address": officer_address,
            "role_id": role_id,
            "role_name": self.DEPARTMENT_ROLES.get(role_id, "UNKNOWN")
        }
    
    def remove_department_officer(self, officer_address):
        """Remove a department officer"""
        if not Web3.is_address(officer_address):
            raise BlockchainError("Invalid Ethereum address format")
        
        receipt = self._call_contract_function("removeDepartmentOfficer", officer_address)
        return {
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "officer_address": officer_address
        }
    
    def get_officer_role(self, officer_address):
        """Get the role of a department officer"""
        if not Web3.is_address(officer_address):
            raise BlockchainError("Invalid Ethereum address format")
        
        role_id = self._call_contract_view("officerRoles", officer_address)
        role_name = self.DEPARTMENT_ROLES.get(role_id, "UNKNOWN")
        
        return {
            "officer_address": officer_address,
            "role_id": role_id,
            "role_name": role_name
        }
    
    def is_authorized_officer(self, officer_address):
        """Check if an address is an authorized officer"""
        if not Web3.is_address(officer_address):
            raise BlockchainError("Invalid Ethereum address format")
        
        is_authorized = self._call_contract_view("authorizedOfficers", officer_address)
        return {
            "officer_address": officer_address,
            "is_authorized": is_authorized
        }
    
    # Certificate operations
    def generate_certificate_hash(self, license_id):
        """Generate a certificate hash for a license"""
        certificate_hash = self._call_contract_view("generateCertificateHash", int(license_id))
        return {
            "license_id": license_id,
            "certificate_hash": certificate_hash.hex()
        }
    
    def verify_certificate(self, license_id):
        """Verify a certificate for a license"""
        result = self._call_contract_view("verifyCertificate", int(license_id))
        is_valid, license_type, farmer_name, approval_date, expiry_date = result
        
        return {
            "license_id": license_id,
            "is_valid": is_valid,
            "license_type": license_type,
            "license_type_name": self.LICENSE_TYPES.get(license_type, "UNKNOWN"),
            "farmer_name": farmer_name,
            "approval_date": datetime.fromtimestamp(approval_date).isoformat() if approval_date else None,
            "expiry_date": datetime.fromtimestamp(expiry_date).isoformat() if expiry_date else None
        }