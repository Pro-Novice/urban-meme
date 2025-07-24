import json, logging, os
from typing import Any, List, Dict, Optional, Tuple
from django.conf import settings
from web3 import Web3
from web3.exceptions import ContractLogicError
from datetime import datetime
from .models import BlockchainEvent
from seed_license.enums import OfficerRole, DivisionEnum

logger = logging.getLogger(__name__)

# ── connect ───────────────────────────────────────────────────────────
w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL))
if not w3.is_connected():
    raise ConnectionError("Cannot connect to blockchain node")

# ── single signer (service account) ───────────────────────────────────
DEFAULT_PRIVATE_KEY = settings.PRIVATE_KEY
if not DEFAULT_PRIVATE_KEY:
    raise RuntimeError("settings.PRIVATE_KEY is missing – add it to .env")
DEFAULT_ACCOUNT = w3.eth.account.from_key(DEFAULT_PRIVATE_KEY)
DEFAULT_ADDRESS = DEFAULT_ACCOUNT.address

# ── helpers ───────────────────────────────────────────────────────────

BASE_DIR = settings.BASE_DIR
CONTRACTS_DIR = os.path.join(BASE_DIR, "Services", "blockchain", "contracts")

# Matches LicenseCategory enum in smart contract
LICENSE_CATEGORIES = ["SEED", "FERTILIZER", "INSECTICIDE"]

ACTION_TYPES = [
    "CREATED", "SUBMITTED", "DOCUMENT_UPLOADED", "DOCUMENT_VERIFIED",
    "INSPECTION_SCHEDULED", "INSPECTION_COMPLETED",
    "STATUS_UPDATED", "APPROVED", "REJECTED", "REVOKED", "RENEWED",
    "COMMENT_ADDED", "OFFICER_ASSIGNED"
]

#Admin levels as per smart contract
ADMIN_LEVELS = ["STATE", "DIVISION", "DISTRICT"]

# Matches LicenseStatus enum in smart contract
# Note: Ensure this matches the enum in your Solidity contract
LICENSE_STATUSES = [
    "DRAFT", "SUBMITTED", "UNDER_REVIEW", "DOCUMENTS_VERIFIED", "INSPECTION_SCHEDULED",
    "INSPECTION_COMPLETED", "APPROVED", "REJECTED", "REVOKED",
    "EXPIRED", "RENEWAL_PENDING"
]

FEEDBACK_TYPES = ["None", "Satisfactory", "Unsatisfactory", "Needs Reinspection"]

# generic transform map for contract methods
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

    # 🌟 Remove irrelevant date fields based on status
    if status_str != "APPROVED":
       transformed.pop("approvalDate", None)

    if status_str not in {"APPROVED", "EXPIRED"}:
        transformed.pop("expiryDate", None)

    if status_str != "REJECTED":
        transformed.pop("rejectionDate", None)

    if status_str != "REVOKED":
        transformed.pop("revokedDate", None)

    if status_str not in {"RENEWAL_PENDING", "RENEWED"}:
        transformed.pop("renewalDate", None)

    return transformed


# convert timestamp to readable format
def format_unix_timestamp(ts: int) -> str:
    if not ts or ts == 0:
        return None
    return datetime.utcfromtimestamp(ts).strftime("%d %B %Y")

# Format contract result based on method name and contract ABI
def format_api_response(success: bool, data: Any = None, error: str = None, extra: Dict = None) -> Dict:
    # Auto unwrap if already wrapped (defensive)
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
            "licenseId", "applicantName", "category", "level", "status",
            "applicant", "businessName", "district","state","division","applicationDate", "approvalDate","rejectionDate",  "expiryDate", "revokedDate", "renewalDate", "isActive",
        ],
        "enum_mappings": {
            "category": LICENSE_CATEGORIES,
            "level": ADMIN_LEVELS,
            "status": LICENSE_STATUSES
        },
        "timestamp_fields": ["applicationDate", "approvalDate", "rejectionDate", "expiryDate", "revokedDate", "renewalDate"]
    },
    "getOfficerInfo": {
        "fields": [
            "officerAddress", "name", "employeeId", "role",
            "department", "level", "jurisdiction", "isActive", "addedDate"
        ],
        "enum_mappings": {"level": ADMIN_LEVELS},
        "timestamp_fields": ["addedDate"]
    },
    "getOfficerDetails": {
        "fields": [
            "name", "employeeId", "role", "department", "level",
            "jurisdiction", "isActive", "addedDate"
        ],
        "enum_mappings": {"level": ADMIN_LEVELS},
        "timestamp_fields": ["addedDate"]
    },
    "getLicenseStatusHistory": {
        "fields": [
            "timestamp", "actionType", "actor", "actorName",
            "actorRole", "department", "remarks", "dataHash"
        ],
        "enum_mappings": {"actionType": ACTION_TYPES},
        "timestamp_fields": ["timestamp"]
    },
    "getLicenseActionHistory": {
        "fields": [
            "timestamp", "actionType", "actor", "actorName",
            "actorRole", "department", "remarks", "dataHash"
        ],
        "enum_mappings": {"actionType": ACTION_TYPES},
        "timestamp_fields": ["timestamp"]
    },
    "getOfficerAssignment": {
        "fields": [
            "officer", "role", "department", "assignedDate",
            "assignedBy", "isActive", "remarks"
        ],
        "timestamp_fields": ["assignedDate"]
    },
    "getOfficerRole": {
        "fields": ["role"]
    },
    "listAllFunctions": {
        "fields": []
    },
    "getAllInspectionFeedback": {
        "fields": [
            "inspector", "inspectorName", "remarks", "completedDate", "feedbackType"
        ],
        "enum_mappings": {"feedbackType": FEEDBACK_TYPES},
        "timestamp_fields": ["completedDate"]
    }

    # add more methods as needed
}

# Format contract result based on method name and contract ABI
def format_and_transform_response(result: Any, method_name: str, contract: Any) -> Any:
    """
    Formats and transforms a contract read response.
    Applies field names, enum mappings, and timestamp formatting based on GENERIC_TRANSFORM_MAP.
    """
    base_formatted = format_contract_result(result, method_name, contract)

    config = GENERIC_TRANSFORM_MAP.get(method_name)
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


def get_contract(contract_name: str):
    """Load ABI + address and return web3 Contract."""
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
        # Check if we have a mapping for this contract name
        abi_found = False

        # Always use proxy address for upgradeable contracts
        proxy_address = deployment_info.get("proxy")
        if not proxy_address:
            raise ValueError("Proxy address not found in deployment_info.json")

        abi = None
        abi_found = False

        # Priority 1: If ABI is already embedded in deployment_info.json
        if "implementationABI" in deployment_info and deployment_info["implementationABI"]:
            abi = deployment_info["implementationABI"]
            abi_found = True
            logger.info("✅ Using embedded implementation ABI from deployment_info.json")

        # Priority 2: Fallback locations if ABI wasn't found in JSON
        if not abi_found:
            abi_locations = [
                os.path.join(BASE_DIR, "blockchainDeploymentScripts", "implementationABI", f"{contract_name}.json"),
                os.path.join(BASE_DIR, "blockchainDeploymentScripts", f"{contract_name}ImplementationABI.json"),
                os.path.join(CONTRACTS_DIR, "abi", f"{contract_name}.json"),
                os.path.join(CONTRACTS_DIR, "abi", "seedLicenseContract.json"),  # for legacy support
            ]
            for path in abi_locations:
                if os.path.exists(path):
                    with open(path, "r") as f:
                        abi = json.load(f)
                    abi_found = True
                    logger.info(f"✅ Loaded ABI from: {path}")
                    break

        if not abi or not abi_found:
            raise FileNotFoundError(f"ABI for {contract_name} not found in any known location")

        # Create contract instance
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(proxy_address),
            abi=abi
        )

        # Cache and return
        _contract_cache[contract_name] = contract
        logger.info(f"✅ Contract {contract_name} loaded successfully with proxy: {proxy_address}")
        return contract
        
    except FileNotFoundError as e:
        logger.error(f"File not found when loading contract {contract_name}: {e}")
        raise ValueError(f"Contract configuration not found. Please ensure ABI files are in the correct location.")
    except Exception as exc:
        logger.error(f"Contract loading error for {contract_name}: {exc}")
        raise


def _sign_and_send(tx: dict, private_key: str) -> str:
    signed = w3.eth.account.sign_transaction(tx, private_key)
    return w3.eth.send_raw_transaction(signed.raw_transaction)

def call_function(function, *args, address=None, private_key=None) -> Tuple[Any, Any]:
    """
    Enhanced function to build, sign & send a state-changing transaction and wait for receipt.
    Now returns both receipt and return value.
    """
    sender = address or DEFAULT_ADDRESS
    key = private_key or DEFAULT_PRIVATE_KEY
    
    logger.info(f"🔍 TRANSACTION DEBUG - Starting call_function")
    logger.info(f"From address: {sender}")
    logger.info(f"Function: {function}")
    logger.info(f"Args: {args}")
    
    # Check account balance first
    try:
        balance_wei = w3.eth.get_balance(sender)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        logger.info(f"💰 Account balance: {balance_eth} ETH")
        
        if balance_eth < 0.01:  # Less than 0.01 ETH
            raise ValueError(f"Insufficient balance: {balance_eth} ETH. Need at least 0.01 ETH for transactions.")
    except Exception as e:
        logger.error(f"Failed to check balance: {e}")
    
    # ===== CAPTURE RETURN VALUE BEFORE TRANSACTION =====
    return_value = None
    try:
        # For functions that return values, we need to simulate the call first
        # This gives us the return value that would be returned
        return_value = function(*args).call({"from": sender})
        logger.info(f"✅ Function call simulation successful, return value: {return_value}")
    except Exception as e:
        logger.error(f"❌ Function call simulation failed: {e}")
        # Extract revert reason if available
        error_str = str(e)
        if "execution reverted" in error_str:
            # Try to extract the reason
            if ":" in error_str:
                reason = error_str.split(":", 1)[1].strip()
                raise ContractLogicError(f"Contract reverted: {reason}")
            else:
                raise ContractLogicError(f"Contract reverted: {error_str}")
        # Continue anyway for some edge cases
    
    # Get current network info for gas optimization
    chain_id = w3.eth.chain_id
    logger.info(f"🌐 Chain ID: {chain_id}")
    
    # Build initial transaction
    try:
        nonce = w3.eth.get_transaction_count(sender, 'pending')
        logger.info(f"📋 Using nonce: {nonce}")
        
        # Get base gas price
        base_gas_price = w3.eth.gas_price
        logger.info(f"⛽ Base gas price: {w3.from_wei(base_gas_price, 'gwei')} gwei")
        
        # Optimize gas price based on network
        if chain_id == 31337:  # Hardhat Network
            # Use minimal gas price for local development
            gas_price = max(base_gas_price, 1000000000)  # At least 1 gwei
            logger.info(f"🔧 Hardhat detected - using minimal gas price: {w3.from_wei(gas_price, 'gwei')} gwei")
        elif chain_id == 1337:  # Ganache
            gas_price = base_gas_price
            logger.info(f"🔧 Ganache detected - using base gas price: {w3.from_wei(gas_price, 'gwei')} gwei")
        else:
            # Real networks need premium for faster confirmation
            gas_price = int(base_gas_price * 1.2)  # 20% premium
            logger.info(f"🌐 Real network - using premium gas price: {w3.from_wei(gas_price, 'gwei')} gwei")
        
        tx = function(*args).build_transaction({
            "from": sender,
            "nonce": nonce,
            "gasPrice": gas_price,
        })
        
        logger.info(f"📝 Initial transaction built successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to build transaction: {e}")
        raise ValueError(f"Transaction building failed: {e}")
    
    # Estimate gas with safety buffer
    try:
        logger.info(f"🔍 Estimating gas...")
        estimated_gas = w3.eth.estimate_gas(tx)
        logger.info(f"📊 Gas estimate: {estimated_gas:,}")
        
        # Apply appropriate buffer based on network
        if chain_id in [31337, 1337]:  # Local networks
            buffer_multiplier = 1.5  # 50% buffer for local testing
        else:
            buffer_multiplier = 1.2  # 20% buffer for real networks
            
        gas_limit = int(estimated_gas * buffer_multiplier)
        
        # Cap gas limit to prevent excessive costs
        max_gas_limit = 1000000  # 1M gas max
        if gas_limit > max_gas_limit:
            logger.warning(f"⚠️ Gas limit {gas_limit:,} exceeds max {max_gas_limit:,}, capping")
            gas_limit = max_gas_limit
            
        tx["gas"] = gas_limit
        logger.info(f"⛽ Using gas limit: {gas_limit:,} (estimate: {estimated_gas:,}, buffer: {buffer_multiplier}x)")
        
    except Exception as e:
        logger.error(f"❌ Gas estimation failed: {e}")
        # Use conservative default based on network
        if chain_id in [31337, 1337]:
            default_gas = 500000  # 500k for local networks
        else:
            default_gas = 300000  # 300k for real networks
            
        tx["gas"] = default_gas
        logger.warning(f"🔄 Using fallback gas limit: {default_gas:,}")
    
    # Calculate and validate transaction cost
    try:
        total_gas_cost_wei = tx["gas"] * tx["gasPrice"]
        total_gas_cost_eth = w3.from_wei(total_gas_cost_wei, 'ether')
        
        logger.info(f"💸 Transaction cost breakdown:")
        logger.info(f"   Gas limit: {tx['gas']:,}")
        logger.info(f"   Gas price: {w3.from_wei(tx['gasPrice'], 'gwei')} gwei")
        logger.info(f"   Max cost: {total_gas_cost_eth:.6f} ETH")
        
        # Check if account can afford the transaction
        balance_wei = w3.eth.get_balance(sender)
        if total_gas_cost_wei >= balance_wei:
            balance_eth = w3.from_wei(balance_wei, 'ether')
            raise ValueError(
                f"Insufficient funds for transaction. "
                f"Need: {total_gas_cost_eth:.6f} ETH, "
                f"Have: {balance_eth:.6f} ETH"
            )
            
        # Warn if transaction cost is high relative to balance
        if total_gas_cost_wei > balance_wei * 0.1:  # More than 10% of balance
            balance_eth = w3.from_wei(balance_wei, 'ether')
            logger.warning(f"⚠️ High transaction cost: {total_gas_cost_eth:.6f} ETH ({total_gas_cost_wei/balance_wei*100:.1f}% of balance)")
            
    except Exception as e:
        logger.error(f"❌ Failed to calculate transaction cost: {e}")
        # Continue anyway - might be a calculation error
    
    # Sign and send transaction
    try:
        logger.info(f"🔍 Signing and sending transaction...")
        tx_hash = _sign_and_send(tx, key)
        logger.info(f"📡 Transaction sent: {tx_hash.hex()}")
        
        # Wait for confirmation with timeout
        logger.info(f"⏳ Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
       
       
        print(f"   Status ==>>>>: {receipt}")
       
        if receipt.status == 1:
            logger.info(f"✅ Transaction confirmed in block {receipt.blockNumber}")
            logger.info(f"⛽ Gas used: {receipt.gasUsed:,} / {tx['gas']:,} ({receipt.gasUsed/tx['gas']*100:.1f}%)")
        else:
            logger.error(f"❌ Transaction failed in block {receipt.blockNumber}")
        
        # ===== RETURN BOTH RECEIPT AND RETURN VALUE =====
        logger.info(f"📤 Returning receipt and return value: {return_value}")
        return receipt, return_value
        
    except Exception as e:
        logger.error(f"❌ Transaction failed: {e}")
        
        # Handle specific Web3 errors
        error_msg = str(e).lower()
        
        if "insufficient funds" in error_msg:
            raise ValueError(f"Insufficient funds for transaction: {e}")
        elif "nonce too low" in error_msg:
            raise ValueError(f"Nonce too low - transaction ordering issue: {e}")
        elif "already known" in error_msg:
            raise ValueError(f"Transaction already in mempool: {e}")
        elif "underpriced" in error_msg:
            raise ValueError(f"Gas price too low: {e}")
        elif "intrinsic gas too low" in error_msg:
            raise ValueError(f"Gas limit too low: {e}")
        else:
            raise ValueError(f"Transaction failed: {e}")


def call_view_function(function, *args):
    """Read‑only contract call."""
    return function(*args).call()


def get_transaction_status(tx_hash: str):
    """Return Tx status + meta used by `/blockchain/transactions/*` APIs."""
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


# ══════════════════════════════════════════════════════════════════════
# Enhanced Event Parsing
# ══════════════════════════════════════════════════════════════════════

def parse_receipt_events(receipt: Any, contract: Any) -> List[Dict[str, Any]]:
    """
    Enhanced event parsing to extract license IDs and other important data
    """
    events = []
    
    try:
        # Get all events from the contract ABI
        contract_events = {}
        
        # Dynamically get all event names from contract ABI
        for abi_item in contract.abi:
            if abi_item.get('type') == 'event':
                event_name = abi_item['name']
                try:
                    contract_events[event_name] = getattr(contract.events, event_name)
                except AttributeError:
                    logger.warning(f"Event {event_name} not found in contract.events")
        
        logger.info(f"Found {len(contract_events)} events in contract: {list(contract_events.keys())}")
        
        for log in receipt.logs:
            event_parsed = False
            for event_name, event_filter in contract_events.items():
                try:
                    decoded_log = event_filter().processLog(log)
                    
                    # Base event data
                    event_data = {
                        "event": event_name,
                        "block_number": decoded_log.blockNumber,
                        "transaction_hash": decoded_log.transactionHash.hex(),
                        "log_index": decoded_log.logIndex,
                        "address": decoded_log.address
                    }
                    
                    # Parse specific events with their arguments
                    if event_name == 'LicenseApplied':
                        event_data.update({
                            "license_id": decoded_log.args.licenseId,
                            "farmer_address": decoded_log.args.farmerAddress,
                            "license_type": decoded_log.args.licenseType
                        })
                    elif event_name == 'LicenseStatusUpdated':
                        event_data.update({
                            "license_id": decoded_log.args.licenseId,
                            "previous_status": decoded_log.args.previousStatus,
                            "new_status": decoded_log.args.newStatus,
                            "officer_address": decoded_log.args.officerAddress
                        })
                    elif event_name == 'LicenseRevoked':
                        event_data.update({
                            "license_id": decoded_log.args.licenseId,
                            "officer_address": decoded_log.args.officerAddress,
                            "reason": decoded_log.args.reason
                        })
                    elif event_name == 'OfficerAdded':
                        event_data.update({
                            "officer_address": decoded_log.args.officerAddress,
                            "role": decoded_log.args.role
                        })
                    elif event_name == 'OfficerRemoved':
                        event_data.update({
                            "officer_address": decoded_log.args.officerAddress
                        })
                    else:
                        # Generic event parsing - add all arguments
                        event_data["args"] = dict(decoded_log.args)
                    
                    events.append(event_data)
                    logger.info(f"Parsed event: {event_name} - {event_data}")
                    event_parsed = True
                    break  # Successfully parsed, move to next log
                    
                except Exception as parse_error:
                    # This log doesn't match this event type, continue to next
                    continue
            
            # If no event matched, add raw log data
            if not event_parsed:
                try:
                    events.append({
                        "event": "Unknown",
                        "topics": [topic.hex() for topic in log.get('topics', [])],
                        "data": log.get('data', '').hex() if log.get('data') else '0x',
                        "address": log.get('address', ''),
                        "block_number": log.get('blockNumber'),
                        "log_index": log.get('logIndex')
                    })
                except Exception as e:
                    logger.warning(f"Could not parse unknown log: {e}")
                    
    except Exception as e:
        logger.warning(f"Could not parse events: {e}")
    
    return events

def _get_network_info():
    """Helper function to get network information for error responses"""
    try:
        network_names = {
            1: "Ethereum Mainnet",
            56: "BSC Mainnet",
            97: "BSC Testnet", 
            137: "Polygon Mainnet",
            80001: "Polygon Mumbai",
            1337: "Ganache",
            31337: "Hardhat Network",
            11155111: "Sepolia",
            5: "Goerli"
        }
        
        return {
            "rpc_url": str(w3.provider.endpoint_uri) if hasattr(w3.provider, 'endpoint_uri') else "unknown",
            "chain_id": w3.eth.chain_id if w3.is_connected() else "unknown",
            "network_name": network_names.get(w3.eth.chain_id, f"Unknown (ID: {w3.eth.chain_id})") if w3.is_connected() else "unknown",
            "connected": w3.is_connected()
        }
    except Exception:
        return {
            "rpc_url": "error",
            "chain_id": "error", 
            "network_name": "error",
            "connected": False
        }


# ══════════════════════════════════════════════════════════════════════
# Enhanced Write to Contract Function
# ══════════════════════════════════════════════════════════════════════

def write_to_contract(contract_name: str, method_name: str, params: List[Any], 
                               address: Optional[str] = None, private_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimized function to write to smart contract
    - Validates method and parameters against ABI from deployment_info.json
    - Executes transaction with minimal overhead
    - Returns clean response
    """
    try:
        # =============== LOAD CONTRACT FROM DEPLOYMENT INFO ===============
        deployment_info_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")
        
        if not os.path.exists(deployment_info_path):
            return {
                "success": False,
                "error": "Deployment info not found",
                "details": f"File not found: {deployment_info_path}"
            }
        
        with open(deployment_info_path, "r") as fh:
            deployment_info = json.load(fh)
        
        # Get contract address (always use proxy for upgradeable contracts)
        contract_address = deployment_info.get("proxy")
        if not contract_address:
            return {
                "success": False,
                "error": "Contract address not found",
                "details": "No proxy address in deployment_info.json"
            }
        
        # Get ABI
        abi = deployment_info.get("implementationABI")
        if not abi:
            return {
                "success": False,
                "error": "Contract ABI not found",
                "details": "No implementationABI in deployment_info.json"
            }
        
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
        
        # =============== CREATE CONTRACT INSTANCE ===============
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi
        )
        if method_name == "addOfficer":
            # Convert role param (index 3)
            try:
                role_param = params[3]
                if isinstance(role_param, str):
                    role_enum = OfficerRole.from_string(role_param).value
                    params[3] = role_enum
            except (IndexError, ValueError) as e:
                return {
                    "success": False,
                    "error": "Invalid role parameter",
                    "details": str(e)
                }

            # Convert based on level param (index 5)
            level = params[5]

            if level == 0:  # STATE
                params[6] = "RAJASTHAN" # Rajasthan enum value, adjust as needed
                params[7] = -1  # division empty
                params[8] = -1  #district empty

            elif level == 1:  # DIVISION
                try:
                    division_param = params[8]
                    if isinstance(division_param, str):
                        division_enum = DivisionEnum.from_string(division_param)
                        params[8] = division_enum
                except (IndexError, ValueError) as e:
                    return {
                        "success": False,
                        "error": "Invalid division parameter",
                        "details": str(e)
                    }

            # elif level == 2:  # DISTRICT
            #     try:
            #         district_param = params[8]
            #         if isinstance(district_param, str):
            #             district_enum = CityEnum.from_string(district_param).value
            #             params[8] = district_enum
            #         params[6] = -1  # state empty
            #         params[7] = -1  # division empty
            #     except (IndexError, ValueError) as e:
            #         return {
            #             "success": False,
            #             "error": "Invalid district parameter",
            #             "details": str(e)
            #         }

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
        
        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        # =============== PARSE EVENTS FOR LICENSE ID ===============
        license_id = None
        events = []
        
        try:
            for log in receipt.logs:
                if log.address.lower() == contract_address.lower():
                    # Try to parse known events
                    try:
                        if len(log.topics) > 0:
                            # LicenseCreated event has license ID in first indexed parameter
                            decoded_log = contract.events.LicenseCreated().process_log(log)
                            license_id = decoded_log.args.licenseId
                            events.append({
                                "event": "LicenseCreated",
                                "license_id": license_id,
                                "applicant": decoded_log.args.applicant,
                                "category": decoded_log.args.category
                            })
                            break
                    except:
                        # Try other events
                        try:
                            decoded_log = contract.events.StatusChanged().process_log(log)
                            events.append({
                                "event": "StatusChanged", 
                                "license_id": decoded_log.args.licenseId,
                                "old_status": decoded_log.args.oldStatus,
                                "new_status": decoded_log.args.newStatus,
                                "changed_by": decoded_log.args.changedBy
                            })
                        except:
                            continue
        except Exception as e:
            logger.warning(f"Could not parse events: {e}")
        
        # =============== BUILD CLEAN RESPONSE ===============
        response = {
            "success": receipt.status == 1,
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




def read_from_contract(contract_name: str, method_name: str, params: List[Any]) -> Any:
    """
    Universal function to read from any smart contract method
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


def format_contract_result(result: Any, method_name: str, contract: Any) -> Any:
    """
    Format the result based on the method's return type
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

def get_contract_abi(contract_name: str) -> List[Dict]:
    """Get the ABI for a contract"""
    contract = get_contract(contract_name)
    return contract.abi


def get_all_contract_addresses() -> dict:
    """
    Get all deployed contract addresses
    Returns a dictionary with contract names and their addresses
    """
    deployment_info_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")
    
    try:
        with open(deployment_info_path, "r") as fh:
            deployment_info = json.load(fh)
        
        addresses = {}
        
        # Add proxy address (recommended for interactions)
        if "proxy" in deployment_info and deployment_info["proxy"]:
            addresses["proxy"] = deployment_info["proxy"]
            addresses["LicenseSystemV1"] = deployment_info["proxy"]  # V1 uses proxy
            addresses["seedLicenseContract"] = deployment_info["proxy"]  # Legacy alias
        
        # Add implementation addresses
        if "implementationV1" in deployment_info:
            addresses["implementationV1"] = deployment_info["implementationV1"]
            addresses["LicenseSystemV1Implementation"] = deployment_info["implementationV1"]
        
        if "implementationV2" in deployment_info:
            addresses["implementationV2"] = deployment_info["implementationV2"]
            addresses["LicenseSystemV2Implementation"] = deployment_info["implementationV2"]
            addresses["LicenseSystemV2"] = deployment_info["implementationV2"]
        
        # Add any other contract addresses found in deployment_info
        excluded_keys = {"network", "networkName", "deploymentTime", "deploymentTimeFormatted", 
                        "deployer", "implementationABI", "gasUsed", "verification"}
        
        for key, value in deployment_info.items():
            if key not in excluded_keys and isinstance(value, str) and value.startswith("0x"):
                if key not in addresses:
                    addresses[key] = value
        
        return {
            "addresses": addresses,
            "total_contracts": len(addresses),
            "recommended_address": deployment_info.get("proxy"),
            "network": deployment_info.get("network"),
            "deployer": deployment_info.get("deployer")
        }
        
    except Exception as e:
        logger.error(f"Error reading deployment info: {e}")
        return {
            "error": f"Failed to read deployment info: {str(e)}",
            "addresses": {}
        }


def get_contract_address(contract_name: str) -> str:
    """
    Get the address for a specific contract
    For upgradeable contracts, this returns the PROXY address (the main interaction point)
    """
    deployment_info_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")
    
    try:
        with open(deployment_info_path, "r") as fh:
            deployment_info = json.load(fh)
        
        # Contract name to deployment key mapping
        contract_mapping = {
            # Proxy addresses (recommended for interaction)
            "LicenseSystemV1": "proxy",
            "LicenseSystemV2": "proxy", 
            "seedLicenseContract": "proxy",
            "proxy": "proxy",
            "ERC1967Proxy": "proxy",
            
            # Implementation addresses (for direct access)
            "LicenseSystemV1Implementation": "implementationV1",
            "LicenseSystemV2Implementation": "implementationV2",
            "implementationV1": "implementationV1",
            "implementationV2": "implementationV2",
        }
        
        # Get deployment key for the contract name
        deployment_key = contract_mapping.get(contract_name, contract_name)
        
        # Get address from deployment info
        contract_address = deployment_info.get(deployment_key)
        w3.eth.get_code(contract_address)
        
        if contract_address:
            return contract_address
        else:
            raise ValueError(f"Contract address not found for {contract_name}")
            
    except Exception as e:
        logger.error(f"Error getting contract address for {contract_name}: {e}")
        # Fallback to getting from contract instance
        try:
            contract = get_contract(contract_name)
            return contract.address
        except:
            raise ValueError(f"Contract address not found for {contract_name}: {str(e)}")


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


def estimate_gas_for_method(contract_name: str, method_name: str, 
                           params: List[Any], from_address: Optional[str] = None) -> Dict[str, Any]:
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