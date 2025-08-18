import json, logging, os
from typing import Any, List, Dict, Optional, Tuple
from django.conf import settings
from web3 import Web3
from web3._utils.events import get_event_data
from web3.exceptions import ContractLogicError
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime, timezone
from .models import BlockchainEvent
from seed_license.enums import REVERSE_OFFICER_ROLE, LICENSE_STATUS_REVERSE, USER_ROLE, \
    REVERSE_LICENSE_CATEGORY, LICENSE_CATEGORIES, LICENSE_LEVELS, LICENSE_STATUSES

logger = logging.getLogger(__name__)

# Connect to blockchain node
w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL))
if not w3.is_connected():
    raise ConnectionError("Cannot connect to blockchain node")

# Add middleware for POA networks
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Default account setup
if not settings.PRIVATE_KEY:
    raise RuntimeError("settings.PRIVATE_KEY is missing - add it to .env")
DEFAULT_ACCOUNT = w3.eth.account.from_key(settings.PRIVATE_KEY)
DEFAULT_ADDRESS = DEFAULT_ACCOUNT.address
DEFAULT_PRIVATE_KEY = settings.PRIVATE_KEY

# Path configuration
BASE_DIR = settings.BASE_DIR
DEPLOYMENT_INFO_PATH = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")

# Cache for loaded contracts
_contract_cache = {}

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

def clear_contract_cache():
    """Clear the contract cache to force reload"""
    global _contract_cache
    _contract_cache = {}
    logger.info("Contract cache cleared")

def load_deployment_info() -> Dict:
    """Load and return deployment info from JSON file"""
    try:
        with open(DEPLOYMENT_INFO_PATH, "r") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.error(f"Deployment info file not found: {DEPLOYMENT_INFO_PATH}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in deployment info: {DEPLOYMENT_INFO_PATH}")
        raise

def get_current_implementation_abi(deployment_info: Dict) -> Tuple[str, Dict]:
    """Get ABI for current implementation version"""
    current_version = deployment_info.get("currentImplementation", "V1")
    implementations = deployment_info.get("implementations", {})
    
    # Try current version first
    if current_version in implementations:
        abi = implementations[current_version].get("abi")
        if abi:
            return current_version, abi
    
    # Fallback to V1
    if "V1" in implementations:
        abi = implementations["V1"].get("abi")
        if abi:
            logger.warning(f"Using V1 ABI as fallback (current version {current_version} not found)")
            return "V1", abi
    
    raise FileNotFoundError("ABI not found in any known location")

# ================== CORE FUNCTIONS ================== #
def get_contract(contract_name: str):
    """Get contract instance by name using deployment info"""
    if contract_name in _contract_cache:
        return _contract_cache[contract_name]
    
    try:
        deployment_info = load_deployment_info()
        
        # Get proxy address
        proxy_address = deployment_info.get("proxy")
        if not proxy_address:
            raise ValueError("No proxy address found in deployment_info.json")
        
        # Get ABI for current implementation
        version, abi = get_current_implementation_abi(deployment_info)
        logger.info(f"Using {version} implementation ABI")
        
        # Create and cache contract instance
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(proxy_address),
            abi=abi
        )
        _contract_cache[contract_name] = contract
        logger.info(f"Contract {contract_name} loaded with proxy: {proxy_address}")
        return contract
        
    except Exception as e:
        logger.error(f"Contract loading error: {e}")
        raise

def call_view_function(function, *args):
    """Read-only contract call"""
    return function(*args).call()

def get_transaction_status(tx_hash: str):
    """Return Tx status + meta used by `/blockchain/transactions/*` APIs"""
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
def write_to_contract(contract_name: str, method_name: str, params: List[Any], 
                     address: Optional[str] = None, private_key: Optional[str] = None) -> Dict[str, Any]:
    """Execute state-changing contract method"""
    try:
        contract = get_contract(contract_name)
        abi = contract.abi
        contract_address = contract.address
        
        # Validate method exists
        method_abi = next((item for item in abi 
                          if item.get('type') == 'function' and item.get('name') == method_name), None)
        if not method_abi:
            available_methods = [item['name'] for item in abi if item.get('type') == 'function']
            return {
                "success": False,
                "error": f"Method '{method_name}' not found",
                "available_methods": available_methods
            }
        
        # Validate parameters
        expected_inputs = method_abi.get('inputs', [])
        if len(params) != len(expected_inputs):
            return {
                "success": False,
                "error": "Parameter count mismatch",
                "details": f"Expected {len(expected_inputs)} parameters, got {len(params)}",
                "expected_params": [
                    {"name": inp.get('name', f'param{i}'), "type": inp['type']} 
                    for i, inp in enumerate(expected_inputs)
                ]
            }
        
        # Check method mutability
        if method_abi.get('stateMutability') in ['view', 'pure']:
            return {
                "success": False,
                "error": "Cannot write to view/pure function",
                "details": f"Use read_from_contract instead"
            }

        # Prepare transaction
        contract_function = getattr(contract.functions, method_name)
        processed_params = process_params_for_abi(params, contract_function, contract)
        sender_address = address or DEFAULT_ADDRESS
        sender_private_key = private_key or DEFAULT_PRIVATE_KEY
        nonce = w3.eth.get_transaction_count(sender_address, 'pending')
        
        # Estimate gas
        try:
            test_tx = contract_function(*processed_params).build_transaction({
                'from': sender_address,
                'nonce': nonce,
                'gasPrice': w3.eth.gas_price,
            })
            gas_estimate = w3.eth.estimate_gas(test_tx)
            gas_limit = int(gas_estimate * 1.2)  # 20% buffer
        except Exception as e:
            return {
                "success": False,
                "error": "Gas estimation failed",
                "details": str(e),
                "possible_causes": [
                    "Invalid parameters", "Contract state prevents operation", 
                    "Insufficient permissions", "Contract not initialized"
                ]
            }
        
        # Build, sign, and send transaction
        transaction = contract_function(*processed_params).build_transaction({
            'from': sender_address,
            'gas': gas_limit,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'chainId': w3.eth.chain_id
        })
        signed_tx = w3.eth.account.sign_transaction(transaction, sender_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        # Parse events
        license_id, events = parse_events(receipt, abi, contract_address)
        
        # Build response
        response = {
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "gas_limit": gas_limit,
            "contract_address": contract_address,
            "method": method_name,
            "license_id": license_id,
            "events": events,
            "status": "confirmed" if receipt.status == 1 else "failed"
        }
        
        # Add success message
        if receipt.status == 1:
            response["message"] =  (f"Method '{method_name}' executed successfully")

        return response

    except Exception as e:
        error_msg = str(e)
        error_handlers = {
            "insufficient funds": {
                "error": "Insufficient funds", 
                "details": "Not enough ETH for gas fees"
            },
            "nonce too low": {
                "error": "Nonce error", 
                "details": "Transaction ordering issue"
            },
            "execution reverted": {
                "error": "Transaction reverted",
                "details": "Contract rejected the transaction",
                "possible_solutions": [
                    "Check contract initialization", "Verify sender permissions",
                    "Validate parameters", "Check contract state"
                ]
            }
        }
        
        for key, response in error_handlers.items():
            if key in error_msg.lower():
                return {"success": False, **response}
        
        return {"success": False, "error": "Transaction failed", "details": error_msg}

def read_from_contract(contract_name: str, method_name: str, params: List[Any]) -> Any:
    """Read data from contract view function"""
    try:
        contract = get_contract(contract_name)
        
        # Validate method exists
        if not hasattr(contract.functions, method_name):
            raise ValueError(f"Method '{method_name}' not found")
        
        # Execute call
        contract_function = getattr(contract.functions, method_name)
        processed_params = process_params_for_abi(params, contract_function, contract)
        result = contract_function(*processed_params).call()
        
        # Format response
        return format_and_transform_response(result, method_name, contract)

    except ContractLogicError as e:
        logger.error(f"Contract logic error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error reading from contract: {e}")
        raise

# ================== DATA PROCESSING ================== #
def process_params_for_abi(params: List[Any], contract_function: Any, contract: Any) -> List[Any]:
    """Process parameters according to contract ABI types"""
    # Find function ABI
    function_abi = next(
        (item for item in contract.abi 
         if item.get('type') == 'function' and item.get('name') == contract_function.fn_name),
        None
    )
    if not function_abi:
        return params
    
    inputs = function_abi.get('inputs', [])
    if len(params) != len(inputs):
        logger.warning(f"Parameter count mismatch: expected {len(inputs)}, got {len(params)}")
        return params
    
    processed = []
    for i, (param, input_def) in enumerate(zip(params, inputs)):
        param_type = input_def['type']
        
        try:
            if param_type == 'address':
                processed.append(Web3.to_checksum_address(param))
            elif param_type in ('uint256', 'int256') or param_type.startswith(('uint', 'int')):
                processed.append(int(param))
            elif param_type == 'bool':
                processed.append(bool(param) if not isinstance(param, str) else param.lower() in ('true', '1', 'yes'))
            elif param_type.startswith('bytes32'):
                if isinstance(param, str):
                    hex_bytes = bytes.fromhex(param[2:]) if param.startswith('0x') else param.encode()
                    processed.append(hex_bytes.ljust(32, b'\0')[:32])
                else:
                    processed.append(param)
            elif param_type.startswith('bytes'):
                processed.append(bytes.fromhex(param[2:]) if isinstance(param, str) and param.startswith('0x') else param.encode())
            elif param_type == 'string':
                processed.append(str(param))
            elif '[]' in param_type:  # Array type
                processed.append(json.loads(param) if isinstance(param, str) else list(param))
            else:
                processed.append(param)
        except Exception as e:
            logger.warning(f"Error processing param {i} ({param_type}): {e}")
            processed.append(param)
    
    return processed

def format_and_transform_response(result: Any, method_name: str, contract: Any) -> Any:
    """Format and transform contract read response"""
    base_formatted = format_contract_result(result, method_name, contract)
    config = GENERIC_TRANSFORM_MAP.get(method_name)
    
    if config:
        # Handle single-value responses
        if not isinstance(base_formatted, (list, tuple, dict)) and len(config.get("fields", [])) == 1:
            base_formatted = (base_formatted,)
        return generic_transform(method_name, base_formatted)
    
    return base_formatted

def format_contract_result(result: Any, method_name: str, contract: Any) -> Any:
    """Format contract call result based on its type"""
    if result is None:
        return None
    
    # Simple types
    if isinstance(result, (str, int, bool)):
        return result
    
    # Bytes conversion
    if isinstance(result, bytes):
        return '0x' + result.hex()
    
    # Handle structured outputs
    if isinstance(result, (list, tuple)):
        function_abi = next(
            (item for item in contract.abi 
             if item.get('type') == 'function' and item.get('name') == method_name),
            None
        )
        
        if function_abi:
            outputs = function_abi.get('outputs', [])
            # Create dict for named outputs
            if outputs and all(out.get('name') for out in outputs):
                return {
                    out['name']: format_single_value(
                        result[i] if i < len(result) else None, 
                        out['type']
                    )
                    for i, out in enumerate(outputs)
                }
        
        return [format_single_value(v, '') for v in result]
    
    return result

def format_single_value(value: Any, value_type: str) -> Any:
    """Format a single value based on its type"""
    if value is None:
        return None
    if isinstance(value, bytes):
        return '0x' + value.hex()
    if value_type and 'int' in value_type:
        return int(value)
    if value_type == 'bool':
        return bool(value)
    if value_type == 'address':
        return str(value)
    return value

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
        "APPROVED": ["rejectionDate", "revokedDate"],
        "REJECTED": ["approvalDate", "expiryDate", "revokedDate", "renewalDate"],
        "REVOKED": ["approvalDate", "rejectionDate", "expiryDate", "renewalDate"],
        "EXPIRED": ["approvalDate", "rejectionDate", "revokedDate"],
        "RENEWED": ["rejectionDate", "revokedDate"]
    }
    
    if status_str and status_str in status_cleanup:
        for field in status_cleanup[status_str]:
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
def get_all_contract_addresses() -> dict:
    """Get all deployed contract addresses"""
    try:
        deployment_info = load_deployment_info()
        addresses = {}
        
        # Add proxy address
        if proxy := deployment_info.get("proxy"):
            addresses["proxy"] = proxy
        
        # Add implementations
        if implementations := deployment_info.get("implementations"):
            for version, details in implementations.items():
                if addr := details.get("address"):
                    addresses.update({
                        # f"implementation{version}": addr,
                        f"LicenseSystem{version}": addr,
                    })
        
        return {
            "addresses": addresses,
            "total_contracts": len(addresses),
            "recommended_address": deployment_info.get("proxy"),
            "network": deployment_info.get("network"),
            "deployer": deployment_info.get("deployer"),
            "current_implementation": deployment_info.get("currentImplementation", "V1")
        }
        
    except Exception as e:
        logger.error(f"Error reading deployment info: {e}")
        return {"error": f"Failed to read deployment info: {str(e)}", "addresses": {}}

# Get contract address by contract name
def get_contract_address(contract_name: str) -> Optional[str]:
    """Get contract address by name"""
    try:
        return get_all_contract_addresses()["addresses"].get(contract_name)
    except Exception as e:
        logger.error(f"Error getting contract address: {e}")
        return None

# Get available methods for a contract
def get_available_methods(contract_name: str) -> Dict[str, List[Dict]]:
    """Get all available methods for a contract with details"""
    contract = get_contract(contract_name)
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

def estimate_gas_for_method(contract_name: str, method_name: str, params: List[Any], 
                           from_address: Optional[str] = None) -> Dict[str, Any]:
    """Estimate gas for a contract method call"""
    try:
        contract = get_contract(contract_name)
        
        if not hasattr(contract.functions, method_name):
            raise ValueError(f"Method '{method_name}' not found")
            
        contract_function = getattr(contract.functions, method_name)
        processed_params = process_params_for_abi(params, contract_function, contract)
        
        tx = contract_function(*processed_params).build_transaction({
            "from": from_address or DEFAULT_ADDRESS,
            "gasPrice": w3.eth.gas_price,
        })
        
        gas_estimate = w3.eth.estimate_gas(tx)
        gas_price = w3.eth.gas_price
        
        return {
            "gas_estimate": gas_estimate,
            "gas_price": gas_price,
            "gas_price_gwei": w3.from_wei(gas_price, 'gwei'),
            "estimated_cost_wei": gas_estimate * gas_price,
            "estimated_cost_ether": float(w3.from_wei(gas_estimate * gas_price, 'ether'))
        }
        
    except Exception as e:
        logger.error(f"Gas estimation error: {e}")
        raise
