import logging
from web3.exceptions import ContractLogicError
from .blockchain_services import get_contract, call_function, call_view_function
from agri_backend.enums.enums import LicenseStatus, LicenseType, DepartmentRole
from services.api_response import BlockchainError

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
    
    # License Operations
    def apply_for_license(self, farmer_data, address, private_key=None):
        """Apply for a new seed license"""
        return self._call_function(
            'applyForLicense',
            farmer_data['name'],
            farmer_data['aadhaar'],
            farmer_data['location'],
            LicenseType[farmer_data['license_type']].value,
            farmer_data['seed_variety'],
            farmer_data['crop_type'],
            farmer_data['quantity'],
            farmer_data['quality_params'],
            farmer_data['source'],
            address=address,
            private_key=private_key
        )
    
    def update_license_status(self, license_id, new_status, remarks, address, private_key=None):
        """Update license status"""
        return self._call_function(
            'updateLicenseStatus',
            license_id,
            LicenseStatus[new_status].value,
            remarks,
            b'',  
            address=address,
            private_key=private_key
        )
    
    def get_license_summary(self, license_id):
        """Get license summary"""
        return self._call_view_function('getLicenseSummary', license_id)
    
    def verify_certificate(self, license_id):
        """Verify license certificate"""
        return self._call_view_function('verifyCertificate', license_id)
    
    # Admin Functions
    def add_department_officer(self, officer_address, role, admin_address, private_key=None):
        """Add a department officer"""
        return self._call_function(
            'addDepartmentOfficer',
            officer_address,
            DepartmentRole[role].value,
            address=admin_address,
            private_key=private_key
        )
    
    def remove_department_officer(self, officer_address, admin_address, private_key=None):
        """Remove a department officer"""
        return self._call_function(
            'removeDepartmentOfficer',
            officer_address,
            address=admin_address,
            private_key=private_key
        )