import json, logging, os, threading, requests
import ast
from typing import Any, List, Dict, Optional, Tuple
from django.conf import settings
from web3 import Web3
from web3._utils.events import get_event_data
from web3.exceptions import ContractLogicError
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime, timezone
from celery import shared_task

from apps.seed_licenses.models import EventLog
from apps.seed_licenses.enums import REVERSE_OFFICER_ROLE, LICENSE_STATUS_REVERSE, USER_ROLE, \
    REVERSE_LICENSE_CATEGORY, LICENSE_CATEGORIES, LICENSE_LEVELS, LICENSE_STATUSES

logger = logging.getLogger(__name__)

# ================== CONCURRENCY & PERFORMANCE SETUP ================== #
NONCE_LOCK = threading.Lock()
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('http://', adapter)
session.mount('https://', adapter)

# ================== WEB3 CONNECTION SETUP ================== #
w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL, session=session))
if not w3.is_connected():
    raise ConnectionError("Cannot connect to blockchain node",settings.BLOCKCHAIN_URL)

w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Default account for system operations (admin functions)
if hasattr(settings, 'PRIVATE_KEY') and settings.PRIVATE_KEY:
    DEFAULT_ACCOUNT = w3.eth.account.from_key(settings.PRIVATE_KEY)
    DEFAULT_ADDRESS = DEFAULT_ACCOUNT.address
    DEFAULT_PRIVATE_KEY = settings.PRIVATE_KEY
else:
    DEFAULT_ACCOUNT = None
    DEFAULT_ADDRESS = None
    DEFAULT_PRIVATE_KEY = None

# Path configuration
BASE_DIR = settings.BASE_DIR
DEPLOYMENT_INFO_PATH = os.path.join(BASE_DIR, "blockchain", "deployment_info.json")

# Cache for loaded contracts
_contract = None

# Generic transform map for contract methods
GENERIC_TRANSFORM_MAP = {
    "getLicenseBasicInfo": {
        "fields": [
            "licenseId", "licenseNumber", "applicantName", "category", "level", "status", "firmName", 
            "firmType", "firmAddress", "salePointAddress", "saleStorageAddress", "productionCompany", 
            "cropName", "cropVariety", "registeringOfficeName", "registeringAuthority", "applicationDate", 
            "approvalDate", "rejectionDate", "expiryDate", "revokedDate", "renewalDate", "isActive",
        ],
        "enum_mappings": {
            "category": LICENSE_CATEGORIES,
            "level": LICENSE_LEVELS,
            "status": LICENSE_STATUSES
        },
        "timestamp_fields": ["applicationDate", "approvalDate", "rejectionDate", "expiryDate", "revokedDate", "renewalDate"]
    },
    "getLicenseActionHistory": {
        "fields": ["timestamp", "actionType", "actorName", "actorRole", "remarks", "dataHash"],
        "enum_mappings": {"actionType": LICENSE_STATUSES, "actorRole": USER_ROLE},
        "timestamp_fields": ["timestamp"]
    },
    "getLicenseQRData": {"fields": ["verificationHash", "licenseNumber"]}
}

# ================== HELPER FUNCTIONS ================== #
def format_unix_timestamp(ts: int) -> str:
    """Convert unix timestamp to readable date format"""
    if not ts or ts == 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %B %Y")

def load_deployment_info() -> Dict:
    """Load and return deployment info from JSON file"""
    try:
        with open(DEPLOYMENT_INFO_PATH, "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading deployment info: {e}")
        raise

def get_current_implementation_abi(deployment_info: Dict) -> Tuple[str, Dict]:
    """Get ABI for current implementation version"""
    current_version = deployment_info.get("currentImplementation", "V1")
    implementations = deployment_info.get("implementations", {})
    
    # Try current version first, fallback to V1
    for version in [current_version, "V1"]:
        if version in implementations:
            abi = implementations[version].get("abi")
            if abi:
                if version != current_version:
                    logger.warning(f"Using {version} ABI as fallback")
                return version, abi
    
    raise FileNotFoundError("ABI not found in any known location")

# ================== CORE FUNCTIONS ================== #
def get_contract():
    """Get contract instance using deployment info"""
    global _contract
    if _contract:
        return _contract
    
    try:
        deployment_info = load_deployment_info()
        proxy_address = deployment_info.get("proxy")
        if not proxy_address:
            raise ValueError("No proxy address found in deployment_info.json")
        
        version, abi = get_current_implementation_abi(deployment_info)
        logger.info(f"Using {version} implementation ABI")
        
        _contract = w3.eth.contract(
            address=Web3.to_checksum_address(proxy_address),
            abi=abi
        )
        return _contract
        
    except Exception as e:
        logger.error(f"Contract loading error: {e}")
        raise

def call_view_function(function, *args):
    """Read-only contract call"""
    return function(*args).call()

def get_transaction_status(tx_hash: str):
    """Return Tx status + meta"""
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        block = w3.eth.get_block(receipt.blockNumber)
        return {
            "tx_hash": tx_hash,
            "status": "CONFIRMED" if receipt.status == 1 else "FAILED",
            "block_number": receipt.blockNumber,
            "timestamp": block.timestamp,
            "confirmations": w3.eth.block_number - receipt.blockNumber,
        }
    except Exception as e:
        return {"tx_hash": tx_hash, "status": "PENDING", "error": str(e)}

# ================== CONTRACT INTERACTION ================== #
def write_to_contract(method_name: str, params: List[Any], 
                      address: Optional[str] = None, private_key: Optional[str] = None) -> Dict[str, Any]:
    """Execute state-changing contract method with concurrency protection"""
    try:
        contract = get_contract()
        abi = contract.abi
        contract_address = contract.address
        
        # Validate method exists
        if not hasattr(contract.functions, method_name):
            available_methods = [item['name'] for item in abi if item.get('type') == 'function']
            return {
                "success": False,
                "error": f"Method '{method_name}' not found",
                "available_methods": available_methods
            }
        
        # Check if we have credentials for the transaction
        if not address or not private_key:
            if not DEFAULT_ADDRESS or not DEFAULT_PRIVATE_KEY:
                return {
                    "success": False,
                    "error": "No credentials provided and no default account configured"
                }
            address = DEFAULT_ADDRESS
            private_key = DEFAULT_PRIVATE_KEY
        
        contract_function = getattr(contract.functions, method_name)
        
        # Acquire lock to ensure atomic nonce fetching and transaction sending
        with NONCE_LOCK:
            nonce = w3.eth.get_transaction_count(address, 'pending')
            
            # Build, sign, and send transaction
            transaction = contract_function(*params).build_transaction({
                'from': address,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
                'chainId': w3.eth.chain_id
            })
            
            # Estimate gas with buffer
            gas_estimate = w3.eth.estimate_gas(transaction)
            transaction['gas'] = int(gas_estimate * 1.2)
            
            signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        
        # # Parse events
        # license_id, events = parse_events(receipt, abi, contract_address)
        
        # # Build response
        # response = {
        #     "transaction_hash": receipt.transactionHash.hex(),
        #     "block_number": receipt.blockNumber,
        #     "license_id": license_id,
        #     "events": events,
        #     "status": "confirmed" if receipt.status == 1 else "failed"
        # }
        
        # # Save events to database
        # for event in events:
        #     EventLog.objects.create(
        #         event_name=event.get("event"),
        #         license_id=event.get("license_id") or license_id,
        #         block_number=event.get("block_number") or receipt.blockNumber,
        #         transaction_hash=event.get("transaction_hash") or receipt.transactionHash.hex(),
        #         event_data=event
        #     )

        # return response
        tx_hash_hex = tx_hash.hex()
        process_transaction_confirmation.delay(tx_hash_hex, abi, contract_address)
        
        return {
            "success": True,
            "transaction_hash": tx_hash_hex,
            "status": "pending",
            "message": "Transaction submitted successfully. Use the transaction hash to check status."
        }

    except Exception as e:
        try:
            error_details_str = str(e.args[0])

            error_dict = ast.literal_eval(error_details_str)

            revert_reason = error_dict.get('message', 'Execution reverted with no reason')

            return {"success": False, "error": "Transaction failed", "details": revert_reason}

        except (ValueError, SyntaxError, IndexError, KeyError):
            # If parsing fails for any reason, fall back to a generic message
            return {"success": False, "error": "Transaction failed", "details": str(e)}


def read_from_contract(method_name: str, params: List[Any]) -> Any:
    """Read data from contract view function"""
    try:
        contract = get_contract()
        
        # Validate method exists
        if not hasattr(contract.functions, method_name):
            raise ValueError(f"Method '{method_name}' not found")
        
        # Execute call
        contract_function = getattr(contract.functions, method_name)
        result = contract_function(*params).call()
        
        # Format response
        return format_and_transform_response(result, method_name, contract)

    except ContractLogicError as e:
        logger.error(f"Contract logic error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error reading from contract: {e}")
        try:
            error_details_str = str(e.args[0])
            error_dict = ast.literal_eval(error_details_str)
            revert_reason = error_dict.get('message', 'Execution reverted with no reason')
            raise Exception(revert_reason)
        except (ValueError, SyntaxError, IndexError, KeyError):
            # If parsing fails for any reason, fall back to a generic message
            raise e


# ================== DATA PROCESSING ================== #
def format_and_transform_response(result: Any, method_name: str, contract: Any) -> Any:
    """Format and transform contract read response"""
    config = GENERIC_TRANSFORM_MAP.get(method_name)
    
    if config:
        # Handle single-value responses
        if not isinstance(result, (list, tuple, dict)) and len(config.get("fields", [])) == 1:
            result = (result,)
        return generic_transform(method_name, result)
    
    return result

def generic_transform(method_name: str, raw_data: Any) -> Any:
    """Apply generic transformations to contract data"""
    config = GENERIC_TRANSFORM_MAP.get(method_name)
    if not config or not config.get("fields"):
        return raw_data

    fields = config["fields"]
    enum_mappings = config.get("enum_mappings", {})
    timestamp_fields = set(config.get("timestamp_fields", []))
    status_str = None

    # Handle collections
    if isinstance(raw_data, (list, tuple)) and all(isinstance(item, (list, tuple)) for item in raw_data):
        return [generic_transform(method_name, item) for item in raw_data]
    
    # Transform single item
    transformed = {}
    for i, field in enumerate(fields):
        # Extract value based on data structure
        if isinstance(raw_data, dict):
            value = raw_data.get(field)
        elif isinstance(raw_data, (list, tuple)) and i < len(raw_data):
            value = raw_data[i]
        else:
            value = None
        
        # Apply transformations
        if field == "status" and field in enum_mappings:
            status_str = enum_mappings[field][value] if isinstance(value, int) and value < len(enum_mappings[field]) else "UNKNOWN"
        
        if field in enum_mappings:
            enum_list = enum_mappings[field]
            transformed[field] = enum_list[value] if isinstance(value, int) and value < len(enum_list) else "UNKNOWN"
        elif field in timestamp_fields and value:
            transformed[field] = format_unix_timestamp(value)
        else:
            transformed[field] = value
    
    # Clean up date fields based on status
    status_cleanup = {
        "APPROVED": ["rejectionDate", "revokedDate", "renewalDate"],
        "REJECTED": ["approvalDate", "expiryDate", "revokedDate", "renewalDate"],
        "REVOKED": ["approvalDate", "rejectionDate", "expiryDate", "renewalDate"],
        "EXPIRED": ["approvalDate", "rejectionDate", "revokedDate"],
        "RENEWED": ["rejectionDate", "revokedDate"]
    }
    extra_cleanup_statuses = {"SUBMITTED", "UNDER_REVIEW", "DOCUMENTS_VERIFIED", "INSPECTION_SCHEDULED", "INSPECTION_COMPLETED"}
    all_fields_to_pop = ["approvalDate", "rejectionDate", "expiryDate", "renewalDate", "revokedDate"]

    if status_str:
        if status_str in status_cleanup:
            for field in status_cleanup[status_str]:
                transformed.pop(field, None)

        if status_str in extra_cleanup_statuses:
            for field in all_fields_to_pop:
                transformed.pop(field, None)
    
    return transformed

def parse_events(receipt, abi, contract_address):
    """Parse events from transaction receipt"""
    license_id = None
    events = []
    timestamp_fields = ["approvalDate", "expiryDate", "renewalDate", "rejectionDate", 
                        "revokedDate", "applicationDate", "verifiedDate", "detectedDate", "lastModifiedDate"]

    try:
        for log in receipt.logs:
            if log.address.lower() != contract_address.lower():
                continue

            for abi_event in abi:
                if abi_event.get("type") != "event":
                    continue
                
                try:
                    # Generate event signature
                    input_types = ','.join(i['type'] for i in abi_event['inputs'])
                    event_topic = w3.keccak(text=f"{abi_event['name']}({input_types})").hex()
                    
                    if log.topics[0].hex() != event_topic:
                        continue
                    
                    # Decode event
                    decoded = get_event_data(w3.codec, abi_event, log)
                    event_name = abi_event["name"]
                    event_args = dict(decoded["args"])
                    
                    # Apply transformations
                    for field in timestamp_fields:
                        if field in event_args:
                            event_args[field] = format_unix_timestamp(event_args[field])
                    
                    enum_transforms = {
                        "category": REVERSE_LICENSE_CATEGORY,
                        "oldStatus": LICENSE_STATUS_REVERSE,
                        "newStatus": LICENSE_STATUS_REVERSE,
                        "status": LICENSE_STATUS_REVERSE,
                        "changedByRole": REVERSE_OFFICER_ROLE
                    }
                    
                    for field, mapping in enum_transforms.items():
                        if field in event_args:
                            event_args[field] = mapping.get(event_args[field], event_args[field])
                    
                    # Capture license ID
                    if "licenseId" in event_args:
                        license_id = event_args["licenseId"]
                    
                    events.append({"event": event_name, **event_args})
                    break
                except Exception as e:
                    logger.debug(f"Event decoding error: {e}")
    except Exception as e:
        logger.warning(f"Event parsing failed: {e}")
    
    return license_id, events

# ================== CONTRACT UTILITIES ================== #
def get_contract_address() -> Optional[str]:
    """Get contract address"""
    try:
        deployment_info = load_deployment_info()
        return deployment_info.get("proxy")
    except Exception as e:
        logger.error(f"Error getting contract address: {e}")
        return None

def get_available_methods() -> Dict[str, List[Dict]]:
    """Get all available methods for a contract with details"""
    contract = get_contract()
    read_methods = []
    write_methods = []
    
    for abi_item in contract.abi:
        if abi_item.get('type') != 'function':
            continue
            
        method_info = {
            'name': abi_item['name'],
            'inputs': [
                {'name': inp.get('name', f'param{i}'), 'type': inp['type']}
                for i, inp in enumerate(abi_item.get('inputs', []))
            ],
            'outputs': [
                {'name': out.get('name', f'output{i}'), 'type': out['type']}
                for i, out in enumerate(abi_item.get('outputs', []))
            ]
        }
        
        if abi_item.get('stateMutability') in ['view', 'pure']:
            read_methods.append(method_info)
        else:
            write_methods.append(method_info)
    
    return {
        "read_methods": sorted(read_methods, key=lambda x: x['name']),
        "write_methods": sorted(write_methods, key=lambda x: x['name'])
    }


@shared_task
def process_transaction_confirmation(tx_hash: str, abi: List[Dict], contract_address: str):
    """Background task to process transaction confirmation"""
    try:
        # Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        # Parse events
        license_id, events = parse_events(receipt, abi, contract_address)
        
        # Save events to database
        for event in events:
            EventLog.objects.create(
                event_name=event.get("event"),
                license_id=event.get("license_id") or license_id,
                block_number=event.get("block_number") or receipt.blockNumber,
                transaction_hash=event.get("transaction_hash") or receipt.transactionHash.hex(),
                event_data=event
            )
        
        # Update transaction status in cache/database
        # update_transaction_status(tx_hash, {
        #     "status": "confirmed" if receipt.status == 1 else "failed",
        #     "block_number": receipt.blockNumber,
        #     "license_id": license_id,
        #     "events": events,
        #     "confirmed_at": datetime.now().isoformat()
        # })
        
    except Exception as e:
        logger.error(f"Error processing transaction {tx_hash}: {e}")
        # update_transaction_status(tx_hash, {
        #     "status": "failed",
        #     "error": str(e),
        #     "failed_at": datetime.now().isoformat()
        # })

