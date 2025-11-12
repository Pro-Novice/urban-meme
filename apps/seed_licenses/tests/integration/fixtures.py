import pytest
from unittest.mock import MagicMock
from utils.encrypt_aadhaar import encrypt_aadhaar


# ============================================================================
# INTEGRATION TEST FIXTURES
# ============================================================================

class BlockchainStateManager:
    """Shared blockchain state manager for testing"""
    
    # Class-level state to ensure single instance across all patches
    _shared_state = {
        'licenses': {},
        'counter': 0,
        'owner': "0xFE3B557E8Fb62b89F4916B721be55cEb828dBd73"
    }
    
    def __init__(self):
        # Reference the class-level state
        self.state = self._shared_state
    
    def reset(self):
        """Reset the shared state"""
        self._shared_state['licenses'] = {}
        self._shared_state['counter'] = 0
        print(f"[RESET] State reset. Counter: {self._shared_state['counter']}, Licenses: {len(self._shared_state['licenses'])}")
    
    @property
    def licenses(self):
        return self._shared_state['licenses']
    
    @property
    def counter(self):
        return self._shared_state['counter']
    
    @counter.setter
    def counter(self, value):
        self._shared_state['counter'] = value
    
    @property
    def owner(self):
        return self._shared_state['owner']
    
    def read_from_contract(self, method_name, params):
        print(f"[READ] Method: {method_name}, Counter: {self.counter}, Licenses: {list(self.licenses.keys())}")
        
        if method_name == "owner":
            return self.owner
        
        elif method_name == "licenseIdCounter":
            return self.counter
        
        elif method_name == "getLicenseBasicInfo":
            license_id = params[0]
            if license_id not in self.licenses:
                raise Exception(f"License {license_id} does not exist")
            return self.licenses[license_id]
        
        elif method_name == "getLicenseActionHistory":
            license_id = params[0]
            if license_id not in self.licenses:
                raise Exception(f"License {license_id} does not exist")
            return self.licenses[license_id].get("history", [])
        
        elif method_name == "getLicenseQRData":
            license_id = params[0]
            if license_id not in self.licenses:
                raise Exception(f"License {license_id} does not exist")
            license_data = self.licenses[license_id]
            if not license_data.get("isActive", False):
                raise Exception("License must be active to generate QR data")
            return {
                "verificationHash": license_data.get("verificationHash", ""),
                "licenseNumber": license_data.get("licenseNumber", "")
            }
        
        raise ValueError(f"Method '{method_name}' not found")
    
    def write_to_contract(self, method_name, params):
        print(f"[WRITE] Method: {method_name}, Counter BEFORE: {self.counter}, Licenses: {list(self.licenses.keys())}")
        
        if method_name == "submitLicenseApplication":
            self.counter += 1
            license_id = self.counter
        
            # Handle both list and dict input styles
            struct_input = params[0] if isinstance(params, (list, tuple)) else params
           # Generate blockchain-style license number
            license_number = f"RJSDST{license_id}"  # You can tweak prefix logic later
            self.licenses[license_id] = {
                "licenseId": license_id,
                "licenseNumber": license_number,
                "applicantName": struct_input["applicantName"],
                "category": struct_input["category"],
                "level": struct_input["level"],
                "status": "SUBMITTED",
                "firmName": struct_input["firmName"],
                "firmType": struct_input["firmType"],
                "firmAddress": struct_input["firmAddress"],
                "salePointAddress": struct_input["salePointAddress"],
                "saleStorageAddress": struct_input["saleStorageAddress"],
                "productionCompany": struct_input["productionCompany"],
                "cropName": struct_input["cropName"],
                "cropVariety": struct_input["cropVariety"],
                "registeringOfficeName": struct_input["registeringOfficeName"],
                "registeringAuthority": struct_input["registeringAuthority"],
                "applicantPermanentAddress": struct_input["applicantPermanentAddress"],
                "aadhaarNumber": struct_input["aadhaarNumber"],
                "applicationDate": "2025-11-03",
                "isActive": True,
                "verificationHash": f"hash_{license_id}",
                "history": [{
                    "timestamp": "2025-11-03",
                    "actionType": "SUBMITTED",
                    "actorName": struct_input["applicantName"],
                    "actorRole": "CITIZEN",
                    "remarks": "License Application Successfully Submitted",
                    "dataHash": f"hash_{license_id}"
                }]
            }
            
            print(f"[WRITE] Created license {license_id}. Counter AFTER: {self.counter}, Total licenses: {len(self.licenses)}")
            
            return {
                "success": True,
                "transaction_hash": f"0xtx{license_id}",
                "license_id": license_id
            }

        elif method_name == "updateLicenseStatus":
            license_id, new_status, officer_name, role, remarks, renewal_period = params
            
            print(f"[WRITE] Updating license {license_id}. Available licenses: {list(self.licenses.keys())}")
            
            if license_id not in self.licenses:
                print(f"[WRITE] ERROR: License {license_id} not found!")
                return {
                    "success": False,
                    "error": f"License {license_id} does not exist"
                }
            
            license_data = self.licenses[license_id]
            current_status = license_data["status"]
            print(f"[WRITE] Current status: {current_status}, New status: {new_status}")
            
            # Status mapping
            if isinstance(new_status, int):
                status_map = {
                    0: "SUBMITTED",
                    1: "UNDER_REVIEW",
                    2: "DOCUMENTS_VERIFIED",
                    3: "INSPECTION_SCHEDULED",
                    4: "INSPECTION_COMPLETED",
                    5: "APPROVED",
                    6: "REJECTED",
                }
                new_status = status_map.get(new_status, "UNKNOWN")

            license_data["status"] = str(new_status).upper().replace("_", " ")
            
            # Add to history
            license_data["history"].append({
                "timestamp": "2025-11-03",
                "actionType": new_status,
                "actorName": officer_name,
                "actorRole": role,
                "remarks": remarks,
                "dataHash": f"hash_update_{license_id}"
            })
            
            print(f"[WRITE] Updated license {license_id} to status {license_data['status']}")
            
            return {
                "success": True,
                "transaction_hash": f"0xtx_status_{license_id}_{new_status}"
            }
        
        elif method_name == "updateLicenseDetails":
            license_id = params[0]
            
            if license_id not in self.licenses:
                return {
                    "success": False,
                    "error": f"License {license_id} does not exist"
                }
            
            license_data = self.licenses[license_id]
            
            # Only update if license is approved
            if license_data["status"] != "APPROVED":
                return {
                    "success": False,
                    "error": "Only approved licenses can be edited"
                }
            
            # Update fields
            if params[1]:  # firmName
                license_data["firmName"] = params[1]
            if params[2]:  # firmType
                license_data["firmType"] = params[2]
            if params[3]:  # firmAddress
                license_data["firmAddress"] = params[3]
            if params[4]:  # salePointAddress
                license_data["salePointAddress"] = params[4]
            if params[5]:  # saleStorageAddress
                license_data["saleStorageAddress"] = params[5]
            if params[6]:  # productionCompany
                license_data["productionCompany"] = params[6]
            if params[7]:  # cropName
                license_data["cropName"] = params[7]
            if params[8]:  # cropVariety
                license_data["cropVariety"] = params[8]
            
            return {
                "success": True,
                "transaction_hash": f"0xtx_update_{license_id}"
            }
        
        elif method_name == "verifyLicenseWithHash":
            license_number, expected_hash = params
            
            # Find license by number
            found_license = None
            for lic_id, lic_data in self.licenses.items():
                if lic_data["licenseNumber"] == license_number:
                    found_license = lic_data
                    break
            
            if not found_license:
                return {
                    "success": False,
                    "error": "License not found"
                }
            
            is_valid = found_license.get("verificationHash") == expected_hash
            
            return {
                "success": True,
                "transaction_hash": f"0xtx_verify_{license_number}",
                "is_valid": is_valid
            }
        
        raise ValueError(f"Method '{method_name}' not found")


@pytest.fixture(scope="function")
def blockchain_state():
    """Fixture that provides blockchain state for each test"""
    manager = BlockchainStateManager()
    # Reset at start of each test
    manager.reset()
    yield manager
    # Cleanup after test
    manager.reset()


@pytest.fixture
def complete_license_payload():
    """Complete payload for license application"""
    return {
        "licenseCategory": "SEED",
        "licenseLevel": "STATE",
        "registeringAuthority": "Department of Agriculture",
        "registeringOfficeName": "State Agriculture Office",
        "applicantName": "Rajesh Kumar",
        "aadhaarNumber": encrypt_aadhaar("234567890123"),
        "applicantPermanentAddress": "123 Main St, Jaipur, Rajasthan",
        "firmName": "Kumar Seeds Pvt Ltd",
        "firmType": "Private Limited",
        "firmAddress": "456 Industrial Area, Jaipur",
        "salePointAddress": "789 Market Road, Jaipur",
        "saleStorageAddress": "101 Warehouse District, Jaipur",
        "cropName": "Wheat",
        "cropVariety": "HD-2967",
        "isSeedSelfProduced": False, 
        "productionCompany": "Kumar Seeds Pvt Ltd",
    }