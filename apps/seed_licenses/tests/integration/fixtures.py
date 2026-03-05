import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from utils.encrypt_aadhaar import encrypt_aadhaar
from apps.seed_licenses.services.license_service import LicenseService, TransactionService
from apps.seed_licenses.services.multi_account_manager import multi_account_manager

# Shared blockchain state manager for testing
class BlockchainStateManager:
    """Shared blockchain state manager for testing with new architecture"""
    
    _shared_state = {
        'licenses': {},
        'counter': 0,
        'owner': "0x0000000000000000000000000000000000000001",
        'accounts': [
            {
                "address": "0x0000000000000000000000000000000000000001",
                "private_key": "TEST_PRIVATE_KEY",
                "source": "test",
                "index": 0
            }
        ]
    }
    
    def __init__(self):
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
    
    @property
    def accounts(self):
        return self._shared_state['accounts']
    
    def transform_license_data(self, license_data):
        """Transform license data from tuple/list to dict for testing with enum conversion"""
        if isinstance(license_data, (list, tuple)):
            transformed = {
                "licenseId": license_data[0] if len(license_data) > 0 else None,
                "licenseNumber": license_data[1] if len(license_data) > 1 else None,
                "applicantName": license_data[2] if len(license_data) > 2 else None,
                "category": license_data[3] if len(license_data) > 3 else None,
                "level": license_data[4] if len(license_data) > 4 else None,
                "status": license_data[5] if len(license_data) > 5 else None,
                "firmName": license_data[6] if len(license_data) > 6 else None,
                "firmType": license_data[7] if len(license_data) > 7 else None,
                "firmAddress": license_data[8] if len(license_data) > 8 else None,
                "salePointAddress": license_data[9] if len(license_data) > 9 else None,
                "saleStorageAddress": license_data[10] if len(license_data) > 10 else None,
                "productionCompany": license_data[11] if len(license_data) > 11 else None,
                "cropName": license_data[12] if len(license_data) > 12 else None,
                "cropVariety": license_data[13] if len(license_data) > 13 else None,
                "registeringOfficeName": license_data[14] if len(license_data) > 14 else None,
                "registeringAuthority": license_data[15] if len(license_data) > 15 else None,
                "applicationDate": license_data[16] if len(license_data) > 16 else None,
                "isActive": license_data[22] if len(license_data) > 22 else None,
            }
        else:
            transformed = license_data.copy()
        
        # Convert enum values to strings for testing
        status_map = {
            0: "SUBMITTED",
            1: "UNDER_REVIEW", 
            2: "DOCUMENTS_VERIFIED",
            3: "INSPECTION_SCHEDULED",
            4: "INSPECTION_COMPLETED",
            5: "APPROVED",
            6: "REJECTED",
            7: "REVOKED",
            8: "EXPIRED",
            9: "RENEWED"
        }
        
        if "status" in transformed and isinstance(transformed["status"], int):
            transformed["status"] = status_map.get(transformed["status"], "UNKNOWN")
        
        # Convert category and level if needed
        category_map = {0: "SEED", 1: "FERTILIZER", 2: "INSECTICIDE"}
        level_map = {0: "DISTRICT", 1: "DIVISION", 2: "STATE"}
        
        if "category" in transformed and isinstance(transformed["category"], int):
            transformed["category"] = category_map.get(transformed["category"], "UNKNOWN")
        
        if "level" in transformed and isinstance(transformed["level"], int):
            transformed["level"] = level_map.get(transformed["level"], "UNKNOWN")
        
        return transformed

    # ================== MOCK TRANSACTION SERVICE METHODS ================== #

    def mock_transaction_service_read(self, method_name, params):
        """Mock the TransactionService.read() method"""
        print(f"[TX SERVICE READ] Method: {method_name}, Params: {params}")
        
        if method_name == "owner":
            return self.owner
        
        elif method_name == "licenseIdCounter":
            return self.counter
        
        elif method_name == "getLicenseBasicInfo":
            license_id = params[0]
            if license_id not in self.licenses:
                raise Exception(f"License {license_id} does not exist")
            return self.transform_license_data(self.licenses[license_id])  
        
        elif method_name == "getLicenseActionHistory":
            license_id = params[0]
            if license_id not in self.licenses:
                raise Exception(f"License {license_id} does not exist")
            
            history = self.licenses[license_id].get("history", [])
            
            # Transform enum values in history
            action_type_map = {
                0: "SUBMITTED", 1: "UNDER_REVIEW", 2: "DOCUMENTS_VERIFIED",
                3: "INSPECTION_SCHEDULED", 4: "INSPECTION_COMPLETED", 5: "APPROVED",
                6: "REJECTED", 7: "REVOKED", 8: "EXPIRED", 9: "RENEWED"
            }
            
            role_map = {
                0: "CITIZEN", 1: "AGRICULTURE_OFFICER", 2: "ASSISTANT_AGRICULTURE_OFFICER",
                3: "ASSISTANT_DIRECTOR", 4: "DEPUTY_DIRECTOR", 5: "JOINT_DIRECTOR",
                6: "JOINT_DIRECTOR_INPUT", 7: "FIELD_INSPECTOR"
            }
            
            transformed_history = []
            for item in history:
                transformed_item = item.copy()
                if "actionType" in transformed_item and isinstance(transformed_item["actionType"], int):
                    transformed_item["actionType"] = action_type_map.get(transformed_item["actionType"], "UNKNOWN")
                if "actorRole" in transformed_item and isinstance(transformed_item["actorRole"], int):
                    transformed_item["actorRole"] = role_map.get(transformed_item["actorRole"], "UNKNOWN")
                transformed_history.append(transformed_item)
            
            return transformed_history
        
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
    
    def mock_transaction_service_write(self, method_name, params, address=None, private_key=None):
        """Mock the TransactionService.write() method"""
        print(f"[TX SERVICE WRITE] Method: {method_name}, Params: {params}, Address: {address}")
        address = address or self.accounts[0]["address"]
        if method_name == "submitLicenseApplicationV2":
            self.counter += 1
            license_id = self.counter
        
            struct_input = params[0]
            license_number = struct_input.get("licenseNumber") or f"RJSDST{license_id}"
            
            # Create license with proper structure for new data transformer
            self.licenses[license_id] = {
                "licenseId": license_id,
                "licenseNumber": license_number,
                "applicantName": struct_input["applicantName"],
                "category": struct_input["category"],  # Already enum value from serializer
                "level": struct_input["level"],        # Already enum value from serializer
                "status": 0,  # SUBMITTED enum value
                "firmName": struct_input["firmName"],
                "firmType": struct_input["firmType"],
                "firmAddress": struct_input["firmAddress"],
                "salePointAddress": struct_input["salePointAddress"],
                "saleStorageAddress": struct_input["saleStorageAddress"],
                "productionCompany": struct_input.get("productionCompany", ""),
                "cropName": struct_input["cropName"],
                "cropVariety": struct_input["cropVariety"],
                "registeringOfficeName": struct_input["registeringOfficeName"],
                "registeringAuthority": struct_input["registeringAuthority"],
                "applicantPermanentAddress": struct_input["applicantPermanentAddress"],
                "aadhaarNumber": struct_input["aadhaarNumber"],
                "applicationDate": 1733270400,  # Unix timestamp for 2025-01-03
                "isActive": True,
                "verificationHash": f"hash_{license_id}",
                "history": [{
                    "timestamp": 1733270400,
                    "actionType": 0,  # SUBMITTED enum value
                    "actorName": struct_input["applicantName"],
                    "actorRole": 0,   # CITIZEN enum value
                    "remarks": "License Application Successfully Submitted",
                    "dataHash": f"hash_{license_id}"
                }]
            }
            
            return {
                "success": True,
                "transaction_hash": f"0xtx{license_id}",
                "status": "pending",  # CHANGED: "accepted" → "pending"
                "rpc_url": "http://test:8545",
                "message": "Transaction submitted successfully",
                "sender_address": address or self.accounts[0]["address"]
            }

        elif method_name == "updateLicenseStatus":
            license_id, new_status, officer_name, role, remarks, renewal_period = params
            
            if license_id not in self.licenses:
                return {
                    "success": False,
                    "error": f"License {license_id} does not exist"
                }
            
            license_data = self.licenses[license_id]
            
            # Update status (new_status is already enum value from serializer)
            license_data["status"] = new_status
            
            # Add to history
            license_data["history"].append({
                "timestamp": 1733270400,
                "actionType": new_status,
                "actorName": officer_name,
                "actorRole": role,  # Already enum value from serializer
                "remarks": remarks,
                "dataHash": f"hash_update_{license_id}"
            })
            
            return {
                "success": True,
                "transaction_hash": f"0xtx_status_{license_id}_{new_status}",
                "status": "pending",  
                "rpc_url": "http://test:8545",
                "message": "Transaction submitted successfully",
                "sender_address": address or self.accounts[0]["address"]
            }
        
        elif method_name == "updateLicenseDetails":
            license_id = params[0]
            
            if license_id not in self.licenses:
                return {
                    "success": False,
                    "error": f"License {license_id} does not exist"
                }
            
            license_data = self.licenses[license_id]
            
           
            if license_data["status"] != 5:  # APPROVED enum value
                return {
                    "success": False,
                    "error": "License must be APPROVED to update details"
                }
            
            # Update fields
            update_fields = [
                "firmName", "firmType", "firmAddress", "salePointAddress", 
                "saleStorageAddress", "productionCompany", "cropName", "cropVariety"
            ]
            
            for i, field in enumerate(update_fields, 1):
                if i < len(params) and params[i]:
                    license_data[field] = params[i]
            
            return {
                "success": True,
                "transaction_hash": f"0xtx_update_{license_id}",
                "status": "pending", 
                "rpc_url": "http://test:8545",
                "message": "Transaction submitted successfully",
                "sender_address": address or self.accounts[0]["address"]
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
                "status": "pending",  
                "rpc_url": "http://test:8545",
                "message": "Transaction submitted successfully",
                "verified": is_valid,
                "sender_address": address or self.accounts[0]["address"]
            }
        
        raise ValueError(f"Method '{method_name}' not found")
    
@pytest.fixture(scope="function")
def blockchain_state():
    """Fixture that provides blockchain state for each test"""
    manager = BlockchainStateManager()
    manager.reset()
    yield manager
    manager.reset()


@pytest.fixture
def complete_license_payload():
    """Complete payload for license application"""
    return {
        "licenseCategory": "SEED",
        "licenseLevel": "STATE",
        "registeringAuthority": "Department of Agriculture",
        "registeringOfficeName": "State Agriculture Office",
        "licenseNumber": "RJSDST-TEST-002",
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


@pytest.fixture
def mock_transaction_service(blockchain_state):
    """Mock TransactionService for integration tests"""
    mock_service = MagicMock(spec=TransactionService)
    
    # Mock the read method
    mock_service.read.side_effect = blockchain_state.mock_transaction_service_read
    
    # Mock the write method  
    mock_service.write.side_effect = blockchain_state.mock_transaction_service_write
    
    # Mock other methods
    mock_service.get_status.return_value = {
        "tx_hash": "0xtest123",
        "status": "CONFIRMED",
        "block_number": 12345,
        "timestamp": 1733270400,
        "confirmations": 10
    }
    
    return mock_service


@pytest.fixture
def mock_license_service(mock_transaction_service):
    """Mock LicenseService for integration tests"""
    return LicenseService(mock_transaction_service)


@pytest.fixture
def mock_multi_account_manager(blockchain_state):
    """Mock multi-account manager"""
    with patch('apps.seed_licenses.services.multi_account_manager.multi_account_manager') as mock_manager:
        mock_manager.get_random_account.return_value = blockchain_state.accounts[0]
        mock_manager.get_account_by_address.return_value = blockchain_state.accounts[0]
        mock_manager.get_accounts_info.return_value = [
            {"address": acc["address"], "source": acc["source"], "index": acc["index"]}
            for acc in blockchain_state.accounts
        ]
        yield mock_manager


@pytest.fixture
def mock_event_parser():
    """Mock EventParser for integration tests"""
    mock_parser = MagicMock()
    mock_parser.parse_and_store.return_value = (1, [])
    return mock_parser


@pytest.fixture
def mock_celery_tasks():
    """Mock Celery tasks to avoid background processing"""
    with patch('apps.seed_licenses.services.blockchain.tasks.process_transaction_confirmation.delay') as mock_task:
        mock_task.return_value = None
        yield mock_task
