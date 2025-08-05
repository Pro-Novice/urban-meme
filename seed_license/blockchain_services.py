import json, logging, os
from typing import Any, List, Dict, Union, Optional, Tuple
from django.conf import settings
from web3 import Web3
from web3._utils.events import get_event_data
from web3.exceptions import ContractLogicError
from datetime import datetime, timezone
from .models import BlockchainEvent
from seed_license.enums import REVERSE_OFFICER_ROLE, LICENSE_STATUS_REVERSE, REVERSE_LICENSE_CATEGORY, \
LICENSE_CATEGORIES, LICENSE_LEVELS, LICENSE_STATUSES, USER_ROLE


logger = logging.getLogger(__name__)

# Connect to the blockchain node
w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL))
if not w3.is_connected():
    raise ConnectionError("Cannot connect to blockchain node")

# Default account and private key
DEFAULT_PRIVATE_KEY = settings.PRIVATE_KEY
if not DEFAULT_PRIVATE_KEY:
    raise RuntimeError("settings.PRIVATE_KEY is missing - add it to .env")
DEFAULT_ACCOUNT = w3.eth.account.from_key(DEFAULT_PRIVATE_KEY)
DEFAULT_ADDRESS = DEFAULT_ACCOUNT.address

# Base directory for contracts
BASE_DIR = settings.BASE_DIR
CONTRACTS_DIR = os.path.join(BASE_DIR, "Services", "blockchain", "contracts")


# Generic transform map for contract methods
# This map defines how to transform raw data from contract methods into a more usable format.
def generic_transform(method_name: str, raw_data: Any) -> Any:
    if isinstance(raw_data, (list, tuple)) and all(isinstance(item, (list, tuple)) for item in raw_data):
        # Handle array responses
        return [generic_transform(method_name, item) for item in raw_data]

    config = GENERIC_TRANSFORM_MAP.get(method_name)
    if not config or not config.get("fields"):
        return raw_data

    fields = config.get("fields", [])
    enum_mappings = config.get("enum_mappings", {})
    timestamp_fields = set(config.get("timestamp_fields", []))

    transformed = {}
    status_str = None

    for i, field in enumerate(fields):
        value = None
        if isinstance(raw_data, dict):
            value = raw_data.get(field)
        elif isinstance(raw_data, (list, tuple)) and i < len(raw_data):
            value = raw_data[i]

        if field == "status":
            # Save string version of status to apply conditional filters later
            if field in enum_mappings:
                enum_list = enum_mappings[field]
                status_str = enum_list[value] if isinstance(value, int) and value < len(enum_list) else "UNKNOWN"
            else:
                status_str = value

        if field in enum_mappings:
            enum_list = enum_mappings[field]
            transformed[field] = enum_list[value] if isinstance(value, int) and value < len(enum_list) else "UNKNOWN"
        elif field in timestamp_fields and value:
            transformed[field] = format_unix_timestamp(value)
        else:
            transformed[field] = value

    # Remove irrelevant date fields based on status
    if status_str != "APPROVED":
       transformed.pop("approvalDate", None)

    if status_str not in {"APPROVED", "EXPIRED", "RENEWED"}:
        transformed.pop("expiryDate", None)

    if status_str != "REJECTED":
        transformed.pop("rejectionDate", None)

    if status_str != "REVOKED":
        transformed.pop("revokedDate", None)

    if status_str != "RENEWED":
        transformed.pop("renewalDate", None)

    return transformed


# convert timestamp to readable format
def format_unix_timestamp(ts: int) -> str:
    if not ts or ts == 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %B %Y")


# Format contract result based on method name and contract ABI
def format_api_response(success: bool, data: Any = None, error: str = None, extra: Dict = None) -> Dict:
    if isinstance(data, dict) and "success" in data and "data" in data:
        return data
    response = {"success": success}
    if success:
        response["data"] = data or {}
    else:
        response["data"] = {}
        response["error"] = error or "Unknown error"
    if extra:
        response.update(extra)
    return response


# Unified transformation map for all methods
GENERIC_TRANSFORM_MAP = {
    "getLicenseBasicInfo": {
        "fields": [
            "licenseId", "licenseNumber", "applicantName", "category", "level", "status", "firmName", "firmType", "firmAddress", 
            "salePointAddress", "saleStorageAddress", "productionCompany", "cropName", "cropVariety", "registeringOfficeName", 
            "registeringAuthority", "applicationDate", "approvalDate", "rejectionDate", "expiryDate", "revokedDate", "renewalDate", "isActive",
        ],
        "enum_mappings": {
            "category": LICENSE_CATEGORIES,
            "level": LICENSE_LEVELS,
            "status": LICENSE_STATUSES
        },
        "timestamp_fields": ["applicationDate", "approvalDate", "rejectionDate", "expiryDate", "revokedDate", "renewalDate"]
    },
    "getLicenseActionHistory": {
        "fields": [
            "timestamp", "actionType", "actorName", "actorRole", "remarks", "dataHash"
        ],
        "enum_mappings": {
            "actionType": LICENSE_STATUSES,
            "actorRole": USER_ROLE,
        },
        "timestamp_fields": ["timestamp"]
    },
    "getLicenseQRData": {
        "fields": [
            "verificationHash", "licenseNumber",
        ],
    }

    # add more methods as needed
}


# Format contract result based on method name and contract ABI
def format_and_transform_response(result: Any, method_name: str, contract: Any) -> Any:
    """
    Formats and transforms a contract read response.
    Applies field names, enum mappings, and timestamp formatting based on GENERIC_TRANSFORM_MAP.
    Args:
        result (Any): The raw result from the contract call.
        method_name (str): The name of the contract method being called.
        contract (Any): The contract instance used for the call.
    Returns:    
        Any: Transformed data with field names, enum mappings, and formatted timestamps.
    """
    base_formatted = format_contract_result(result, method_name, contract)

    config = GENERIC_TRANSFORM_MAP.get(method_name)
    # print(f"Formatting method: {method_name} with config: {config}")
    if config:
       # If the method has a config, apply generic transformation
        if not isinstance(base_formatted, (list, tuple, dict)) and len(config.get("fields", [])) == 1:
            base_formatted = (base_formatted,)
        return generic_transform(method_name, base_formatted)

    return base_formatted


# Cache for loaded contracts
_contract_cache = {}

def clear_contract_cache():
    """Clear the contract cache to force reload"""
    global _contract_cache
    _contract_cache = {}
    logger.info("Contract cache cleared")


# Get contract instance by name 
# This function retrieves a contract instance by its name, loading the ABI and address from deployment info.
def get_contract(contract_name: str):
    # Check cache first
    if contract_name in _contract_cache:
        return _contract_cache[contract_name]
    
    try:
        # Path to deployment info
        deployment_info_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")
        
        # Load deployment info
        with open(deployment_info_path, "r") as fh:
            deployment_info = json.load(fh)

        # IMPORTANT: For upgradeable contracts, ALWAYS use the PROXY address
        if "proxy" in deployment_info and deployment_info["proxy"]:
            contract_address = deployment_info["proxy"]
            logger.info(f"Using proxy address for {contract_name}: {contract_address}")
        else:
            raise ValueError(f"No proxy address found in deployment_info.json")
        
        # Determine ABI to use
        abi_found = False

        # Always use proxy address for upgradeable contracts
        proxy_address = deployment_info.get("proxy")
        if not proxy_address:
            raise ValueError("Proxy address not found in deployment_info.json")

        abi = None
        abi_found = False

        if "implementations" in deployment_info:
            # Get current implementation version (default to V1 if missing)
            current_version = deployment_info.get("currentImplementation", "V1")
            
            # Get ABI for current implementation
            if current_version in deployment_info["implementations"]:
                impl_info = deployment_info["implementations"][current_version]
                if "abi" in impl_info and impl_info["abi"]:
                    abi = impl_info["abi"]
                    abi_found = True
                    logger.info(f"Using {current_version} ABI from deployment_info.json")
            
            # Fallback to V1 if current version not found
            if not abi_found and "V1" in deployment_info["implementations"]:
                impl_info = deployment_info["implementations"]["V1"]
                if "abi" in impl_info and impl_info["abi"]:
                    abi = impl_info["abi"]
                    abi_found = True
                    logger.info(f"Using V1 ABI as fallback from deployment_info.json")
        
        if not abi or not abi_found:
            raise FileNotFoundError(f"ABI for {contract_name} not found in any known location")

        # Create contract instance
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(proxy_address),
            abi=abi
        )

        # Cache the contract instance
        _contract_cache[contract_name] = contract
        logger.info(f"✅ Contract {contract_name} loaded successfully with proxy: {proxy_address}")
        return contract
        
    except FileNotFoundError as e:
        logger.error(f"File not found when loading contract {contract_name}: {e}")
        raise ValueError(f"Contract configuration not found. Please ensure ABI files are in the correct location.")
    except Exception as exc:
        logger.error(f"Contract loading error for {contract_name}: {exc}")
        raise

def call_view_function(function, *args):
    """Read‑only contract call."""
    return function(*args).call()


# get transaction status
# This function retrieves the status of a transaction by its hash.
def get_transaction_status(tx_hash: str):
    """Return Tx status + meta used by `/blockchain/transactions/*` APIs.
    Args:
        tx_hash (str): The transaction hash to check.
    Returns:
        Dict[str, Any]: The transaction status and metadata.
    """
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
    except Exception as exc:
        return {"tx_hash": tx_hash, "status": "PENDING", "error": str(exc)}


# Universal function to write to any smart contract method
def write_to_contract(contract_name: str, method_name: str, params: List[Any], address: Optional[str] = None, private_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Function to write to smart contract
    - Validates method and parameters against ABI from deployment_info.json
    - Executes transaction with minimal overhead
    - Returns clean response
    Args:
        contract_name (str): Name of the contract to interact with. 
        method_name (str): Name of the method to call.
        params (List[Any]): List of parameters to pass to the method.
        address (Optional[str]): Address to send the transaction from. Defaults to DEFAULT_ADDRESS.
        private_key (Optional[str]): Private key to sign the transaction. Defaults to DEFAULT_PRIVATE_KEY.
    Returns:
        Dict[str, Any]: Response dictionary with success status, data or error message.
    """
    try:
        # Get contract instance and ABI in one call
        contract = get_contract(contract_name)
        abi = contract.abi
        contract_address = contract.address
        
        # =============== VALIDATE METHOD EXISTS IN ABI ===============
        method_abi = None
        for abi_item in abi:
            if (abi_item.get('type') == 'function' and 
                abi_item.get('name') == method_name):
                method_abi = abi_item
                break
        
        if not method_abi:
            # Get available methods for helpful error
            available_methods = [item['name'] for item in abi if item.get('type') == 'function']
            return {
                "success": False,
                "error": f"Method '{method_name}' not found in contract '{contract_name}'",
                "available_methods": available_methods
            }
        
        # =============== VALIDATE PARAMETERS ===============
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
        
        # Check if method is payable (state-changing)
        if method_abi.get('stateMutability') in ['view', 'pure']:
            return {
                "success": False,
                "error": "Cannot write to view/pure function",
                "details": f"Method '{method_name}' is read-only. Use read_from_contract instead."
            }

        # Get the function
        contract_function = getattr(contract.functions, method_name)
        
        # Process parameters for ABI types
        processed_params = process_params_for_abi(params, contract_function, contract)
        
        # =============== EXECUTE TRANSACTION ===============
        sender_address = address or DEFAULT_ADDRESS
        sender_private_key = private_key or DEFAULT_PRIVATE_KEY
        
        # Build transaction
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
        except Exception as gas_error:
            return {
                "success": False,
                "error": "Gas estimation failed",
                "details": str(gas_error),
                "possible_causes": [
                    "Invalid parameters",
                    "Contract state prevents operation", 
                    "Insufficient permissions",
                    "Contract not initialized"
                ]
            }
        
        # Build final transaction
        transaction = contract_function(*processed_params).build_transaction({
            'from': sender_address,
            'gas': gas_limit,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'chainId': w3.eth.chain_id
        })
        
        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(transaction, sender_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"Transaction sent: {tx_hash.hex()}")
        
        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        # =============== PARSE EVENTS FOR LICENSE ID ===============
        license_id = None
        events = []

        timestamp_fields = ["approvalDate", "expiryDate", "renewalDate", "rejectionDate", "revokedDate", "applicationDate", "verifiedDate", "detectedDate", "lastModifiedDate"]

        try:
            for log in receipt.logs:
                if log.address.lower() != contract_address.lower():
                    continue

                for abi_event in abi:
                    if abi_event.get("type") != "event":
                        continue
                    try:
                        event_topic = w3.keccak(text=f"{abi_event['name']}({','.join(i['type'] for i in abi_event['inputs'])})").hex()
                        if log.topics[0].hex() != event_topic:
                            continue
                        decoded = get_event_data(w3.codec, abi_event, log)
                        event_name = abi_event["name"]
                        event_args = dict(decoded["args"])

                        # Post-process event arguments
                        for field in timestamp_fields:
                            if field in event_args:
                                event_args[field] = format_unix_timestamp(event_args[field])
                        if "category" in event_args:
                            event_args["category"] = REVERSE_LICENSE_CATEGORY.get(event_args["category"], event_args["category"])
                        if "oldStatus" in event_args:
                            event_args["oldStatus"] = LICENSE_STATUS_REVERSE.get(event_args["oldStatus"], event_args["oldStatus"])
                        if "newStatus" in event_args:
                            event_args["newStatus"] = LICENSE_STATUS_REVERSE.get(event_args["newStatus"], event_args["newStatus"])
                        if "status" in event_args:
                            event_args["status"] = LICENSE_STATUS_REVERSE.get(event_args["status"], event_args["status"])
                        if "changedByRole" in event_args:
                            event_args["changedByRole"] = REVERSE_OFFICER_ROLE.get(event_args["changedByRole"], event_args["changedByRole"])   
                
                        if "licenseId" in event_args:
                            license_id = event_args["licenseId"]

                        events.append({
                            "event": event_name,
                            **event_args
                        })
                        break
                    except Exception as decode_err:
                        logger.debug(f"Failed to decode event: {decode_err}")
        except Exception as e:
            logger.warning(f"Could not parse events: {e}")

        
        # =============== BUILD CLEAN RESPONSE ===============
        response = {
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "gas_limit": gas_limit,
            "contract_address": contract_address,
            "method": method_name,
            "status": "confirmed" if receipt.status == 1 else "failed"
        }
        
        # Add license ID if found
        if license_id is not None:
            response["license_id"] = license_id

        # Add events if any
        if events:
            response["events"] = events
        
        # Add method-specific messages
        if receipt.status == 1:
            if method_name == "createLicense":
                response["message"] = f"License created successfully" + (f" with ID: {license_id}" if license_id else "")
            elif method_name == "updateStatus":
                response["message"] = "License status updated successfully"
            elif method_name == "addOfficer":
                response["message"] = "Officer added successfully"
            else:
                response["message"] = f"Method '{method_name}' executed successfully"
        for event in events:
            BlockchainEvent.objects.create(
                event_name=event.get("event"),
                license_id=event.get("license_id"),
                block_number=event.get("block_number") or receipt.blockNumber,
                tx_hash=event.get("transaction_hash") or receipt.transactionHash.hex(),
                address=event.get("address") or contract_address,
                payload=event
            )

        return response

    except Exception as e:
        error_msg = str(e)
        
        # Handle common errors
        if "insufficient funds" in error_msg.lower():
            return {
                "success": False,
                "error": "Insufficient funds",
                "details": "Not enough ETH for gas fees"
            }
        elif "nonce too low" in error_msg.lower():
            return {
                "success": False,
                "error": "Nonce error", 
                "details": "Transaction ordering issue"
            }
        elif "execution reverted" in error_msg.lower():
            return {
                "success": False,
                "error": "Transaction reverted",
                "details": "Contract rejected the transaction",
                "possible_solutions": [
                    "Check if contract is initialized",
                    "Verify sender has required permissions",
                    "Ensure parameters are valid",
                    "Check contract state allows this operation"
                ]
            }
        else:
            return {
                "success": False,
                "error": "Transaction failed",
                "details": error_msg
            }


# Universal function to read from any smart contract method
def read_from_contract(contract_name: str, method_name: str, params: List[Any]) -> Any:
    """
    Universal function to read from any smart contract method
    - Validates method and parameters against ABI from deployment_info.json
    - Returns formatted response
    Args:
        contract_name (str): Name of the contract to interact with.
        method_name (str): Name of the method to call.
        params (List[Any]): List of parameters to pass to the method.
    Returns:
        Any: The result of the contract call, formatted according to the method's return type.  
    """
    try:
        contract = get_contract(contract_name)
        
        # Check if method exists
        if not hasattr(contract.functions, method_name):
            raise ValueError(f"Method '{method_name}' not found in contract '{contract_name}'")
        
        # Get the function
        contract_function = getattr(contract.functions, method_name)
        
        # Process parameters
        processed_params = process_params_for_abi(params, contract_function, contract)
        
        # Call the view function
        result = call_view_function(contract_function, *processed_params)

        # Unified formatting
        return format_and_transform_response(result, method_name, contract)

    except ContractLogicError as e:
        logger.error(f"Contract logic error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error reading from contract: {e}")
        raise


# processes parameters for a contract function based on its ABI
def process_params_for_abi(params: List[Any], contract_function: Any, contract: Any) -> List[Any]:
    """
    Process parameters according to the contract ABI types
    """
    processed = []
    
    # Get function ABI
    function_abi = None
    for abi_item in contract.abi:
        if (abi_item.get('type') == 'function' and 
            abi_item.get('name') == contract_function.fn_name):
            function_abi = abi_item
            break
    
    if not function_abi:
        return params
    
    inputs = function_abi.get('inputs', [])
    
    # Handle case where params length doesn't match inputs
    if len(params) != len(inputs):
        logger.warning(f"Parameter count mismatch: expected {len(inputs)}, got {len(params)}")
        return params
    
    for i, (param, input_def) in enumerate(zip(params, inputs)):
        param_type = input_def['type']
        
        try:
            if param_type == 'address':
                processed.append(Web3.to_checksum_address(param))
            elif param_type == 'uint256' or param_type.startswith('uint'):
                processed.append(int(param))
            elif param_type == 'int256' or param_type.startswith('int'):
                processed.append(int(param))
            elif param_type == 'bool':
                if isinstance(param, str):
                    processed.append(param.lower() in ('true', '1', 'yes'))
                else:
                    processed.append(bool(param))
            elif param_type.startswith('bytes32'):
                if isinstance(param, str):
                    if param.startswith('0x'):
                        # Hex string
                        hex_bytes = bytes.fromhex(param[2:])
                        processed.append(hex_bytes.ljust(32, b'\0')[:32])
                    else:
                        # Regular string - convert to bytes32
                        processed.append(Web3.to_bytes(text=param).ljust(32, b'\0')[:32])
                else:
                    processed.append(param)
            elif param_type.startswith('bytes'):
                if isinstance(param, str):
                    if param.startswith('0x'):
                        processed.append(bytes.fromhex(param[2:]))
                    else:
                        processed.append(param.encode('utf-8'))
                else:
                    processed.append(param)
            elif param_type == 'string':
                processed.append(str(param))
            elif '[]' in param_type:  # Array type
                if isinstance(param, str):
                    # Try to parse JSON string
                    try:
                        processed.append(json.loads(param))
                    except:
                        processed.append([param])
                else:
                    processed.append(list(param))
            else:
                processed.append(param)
                
        except Exception as e:
            logger.warning(f"Error processing param {i} of type {param_type}: {e}")
            processed.append(param)
    
    return processed


# Formats the result of a contract call based on its type
# This is used to format the result of a contract call
def format_contract_result(result: Any, method_name: str, contract: Any) -> Any:
    """
    Format the result based on the method's return type
    - If the result is None, return None
    - If it's a simple type (str, int, bool), return as is
    - If it's a list/tuple, format each item\
    - If it's bytes, convert to hex
    - If the method has named outputs, return a dict with names as keys
    Args:
        result (Any): The raw result from the contract call.
        method_name (str): The name of the method called.   
        contract (Any): The contract instance used for the call.
    Returns:    
        Any: The formatted result, either as a simple type, list, or dict with named outputs.
    """
    if result is None:
        return None
    
    # If it's a simple type, return as is
    if isinstance(result, (str, int, bool)):
        return result
    
    # If it's bytes, convert to hex
    if isinstance(result, bytes):
        return '0x' + result.hex()
    
    # If it's a list/tuple, try to get named outputs from ABI
    if isinstance(result, (list, tuple)):
        # Find function ABI
        function_abi = None
        for abi_item in contract.abi:
            if (abi_item.get('type') == 'function' and 
                abi_item.get('name') == method_name):
                function_abi = abi_item
                break
        
        if function_abi:
            outputs = function_abi.get('outputs', [])
            
            # If we have named outputs, create a dict
            if outputs and all(out.get('name') for out in outputs):
                formatted = {}
                for i, (value, output) in enumerate(zip(result, outputs)):
                    name = output['name']
                    formatted[name] = format_single_value(value, output['type'])
                return formatted
        
        # Otherwise return as list
        return [format_single_value(v, '') for v in result]
    
    return result

# Formats the result of a contract call
def format_single_value(value: Any, value_type: str) -> Any:
    """
    Format a single value based on its type
    """
    if value is None:
        return None
    elif isinstance(value, bytes):
        return '0x' + value.hex()
    elif value_type and 'int' in value_type:
        return int(value)
    elif value_type == 'bool':
        return bool(value)
    elif value_type == 'address':
        return str(value)
    else:
        return value


# ══════════════════════════════════════════════════════════════════════
# Utility Functions for Contract Information
# ══════════════════════════════════════════════════════════════════════
# Get contract instance from deployment info
def get_contract_abi(contract_name: str) -> List[Dict]:
    """Get the ABI for a contract"""
    contract = get_contract(contract_name)
    return contract.abi


# Get all deployed contract addresses
def get_all_contract_addresses() -> dict:
    """
    Returns a dictionary with contract names and their addresses
    """
    deployment_info_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")
    
    try:
        with open(deployment_info_path, "r") as fh:
            deployment_info = json.load(fh)
        
        addresses = {}
        
        # Add proxy address 
        if "proxy" in deployment_info and deployment_info["proxy"]:
            addresses["proxy"] = deployment_info["proxy"]
        
        # Add implementation addresses
        if "implementations" in deployment_info:
            for version, details in deployment_info["implementations"].items():
                if "address" in details:
                    addresses[f"implementation{version}"] = details["address"]
                    addresses[f"LicenseSystem{version}"] = details["address"]
                    addresses[f"LicenseSystem{version}Implementation"] = details["address"]
        
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
        return {
            "error": f"Failed to read deployment info: {str(e)}",
            "addresses": {}
        }


# Get all available methods for a contract
def get_available_methods(contract_name: str) -> Dict[str, List[Dict]]:
    """Get all available methods for a contract with details"""
    contract = get_contract(contract_name)
    
    read_methods = []
    write_methods = []
    
    for abi_item in contract.abi:
        if abi_item.get('type') == 'function':
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

# Estimate gas for a contract method call
def estimate_gas_for_method(contract_name: str, method_name: str, params: List[Any], from_address: Optional[str] = None) -> Dict[str, Any]:
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
        logger.error(f"Error estimating gas: {e}")
        raise