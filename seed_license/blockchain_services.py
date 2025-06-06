import json, logging, os
from typing import Any, List, Dict, Union, Optional
from django.conf import settings
from web3 import Web3
from web3.exceptions import ContractLogicError

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

# Cache for loaded contracts
_contract_cache = {}


def get_contract(contract_name: str):
    """Load ABI + address and return web3 Contract."""
    # Check cache first
    if contract_name in _contract_cache:
        return _contract_cache[contract_name]

    try:
        # Path to deployment info
        deployment_info_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")

        # Load deployment info to get contract address
        with open(deployment_info_path, "r") as fh:
            deployment_info = json.load(fh)

        # IMPORTANT: For upgradeable contracts, we need to use the PROXY address
        # but with the IMPLEMENTATION ABI
        use_proxy = deployment_info.get("proxy") is not None

        if use_proxy:
            # Use proxy address for all contract calls
            contract_address = deployment_info["proxy"]
            logger.info(f"Using proxy address for {contract_name}: {contract_address}")

            # But we need the implementation ABI, not the proxy ABI
            # Try to find the implementation ABI
            abi_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "implementationABI",
                                    "LicenseSystemV1.json")
            if not os.path.exists(abi_path):
                # Try alternate paths
                abi_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts",
                                        "LicenseSystemV1ImplementationABI.json")
                if not os.path.exists(abi_path):
                    abi_path = os.path.join(CONTRACTS_DIR, "abi", f"{contract_name}.json")
                    if not os.path.exists(abi_path):
                        # Fall back to generic ABI
                        abi_path = os.path.join(CONTRACTS_DIR, "abi", "seedLicenseContract.json")
        else:
            # Non-upgradeable contract logic
            # Map contract names to deployment keys
            contract_mapping = {
                "seedLicenseContract": "implementationV1",
                "LicenseSystemV1": "implementationV1",
                "LicenseSystemV2": "implementationV2",
            }

            deployment_key = contract_mapping.get(contract_name, contract_name)
            contract_address = deployment_info.get(deployment_key)

            if not contract_address:
                raise ValueError(f"Contract address not found for {contract_name} in deployment_info.json")

            # Standard ABI path
            abi_path = os.path.join(CONTRACTS_DIR, "abi", f"{contract_name}.json")
            if not os.path.exists(abi_path):
                abi_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts",
                                        f"{contract_name}ImplementationABI.json")

        # Load ABI
        with open(abi_path, "r") as fh:
            abi = json.load(fh)

        # Create contract instance
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi
        )

        # Cache the contract
        _contract_cache[contract_name] = contract

        logger.info(f"Loaded contract {contract_name} at address {contract_address} (proxy={use_proxy})")
        return contract

    except FileNotFoundError as e:
        logger.error(f"File not found when loading contract {contract_name}: {e}")
        raise ValueError(f"Contract files not found for {contract_name}")
    except Exception as exc:
        logger.error(f"Contract loading error for {contract_name}: {exc}")
        raise


def _sign_and_send(tx: dict, private_key: str) -> str:
    signed = w3.eth.account.sign_transaction(tx, private_key)
    return w3.eth.send_raw_transaction(signed.raw_transaction)


def call_function(function, *args, address=None, private_key=None):
    """Build, sign & send a state‑changing transaction and wait for receipt."""
    sender = address or DEFAULT_ADDRESS
    key = private_key or DEFAULT_PRIVATE_KEY

    # First, try to call the function to check for revert reasons
    try:
        result = function(*args).call({"from": sender})
        logger.info(f"Dry run successful, result: {result}")
    except Exception as e:
        logger.error(f"Dry run failed with error: {e}")
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

    tx = function(*args).build_transaction({
        "from": sender,
        "nonce": w3.eth.get_transaction_count(sender),
        "gasPrice": w3.eth.gas_price,
    })

    # Estimate gas with 20% buffer
    try:
        estimated_gas = w3.eth.estimate_gas(tx)
        tx["gas"] = int(estimated_gas * 1.2)
    except Exception as e:
        logger.error(f"Gas estimation failed: {e}")
        # Use a default high gas limit
        tx["gas"] = 3000000

    tx_hash = _sign_and_send(tx, key)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


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
# New Methods for Universal Contract Interaction
# ══════════════════════════════════════════════════════════════════════

def write_to_contract(contract_name: str, method_name: str, params: List[Any],
                      address: Optional[str] = None, private_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Universal function to write to any smart contract method
    """
    try:
        contract = get_contract(contract_name)

        logger.info(f"Contract address being used: {contract.address}")
        logger.info(f"Attempting to call {contract_name}.{method_name} with params: {params}")
        logger.info(f"From address: {address or DEFAULT_ADDRESS}")

        # Check if method exists
        if not hasattr(contract.functions, method_name):
            raise ValueError(f"Method '{method_name}' not found in contract '{contract_name}'")

        # Get the function
        contract_function = getattr(contract.functions, method_name)

        # Process parameters
        processed_params = process_params_for_abi(params, contract_function, contract)
        logger.info(f"Processed params: {processed_params}")

        # Call the function
        receipt = call_function(contract_function, *processed_params, address=address, private_key=private_key)

        # Parse events from receipt
        events = parse_receipt_events(receipt, contract)

        return {
            "success": receipt.status == 1,
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "events": events,
            "status": "confirmed" if receipt.status == 1 else "failed"
        }

    except ContractLogicError as e:
        logger.error(f"Contract logic error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error writing to contract: {e}", exc_info=True)
        raise


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

        # Format the result
        return format_contract_result(result, method_name, contract)

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


def parse_receipt_events(receipt: Any, contract: Any) -> List[Dict[str, Any]]:
    """
    Parse events from transaction receipt
    """
    events = []

    try:
        # Get contract events
        for log in receipt.logs:
            try:
                # Try to parse each log
                for event_name in contract.events:
                    event = getattr(contract.events, event_name)
                    try:
                        decoded = event().process_log(log)
                        events.append({
                            "name": event_name,
                            "args": dict(decoded['args']),
                            "address": log['address'],
                            "block_number": log['blockNumber'],
                            "transaction_index": log['transactionIndex'],
                            "log_index": log['logIndex']
                        })
                        break  # Successfully decoded, move to next log
                    except:
                        continue  # Try next event type

            except Exception as e:
                # If we can't decode, include raw log
                events.append({
                    "name": "Unknown",
                    "topics": [topic.hex() for topic in log.get('topics', [])],
                    "data": log.get('data', '').hex() if log.get('data') else '0x',
                    "address": log.get('address', '')
                })

    except Exception as e:
        logger.warning(f"Error parsing events: {e}")

    return events


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


def get_contract_address(contract_name: str) -> str:
    """Get the address for a contract"""
    # For informational purposes, return the implementation address
    # But note that actual calls go through the proxy
    deployment_info_path = os.path.join(BASE_DIR, "blockchainDeploymentScripts", "deployment_info.json")

    try:
        with open(deployment_info_path, "r") as fh:
            deployment_info = json.load(fh)

        # Map contract names to deployment keys
        contract_mapping = {
            "seedLicenseContract": "implementationV1",
            "LicenseSystemV1": "implementationV1",
            "LicenseSystemV2": "implementationV2",
        }

        deployment_key = contract_mapping.get(contract_name, contract_name)
        implementation_address = deployment_info.get(deployment_key)

        if not implementation_address:
            implementation_address = deployment_info.get(contract_name)

        # Also get proxy if it exists
        proxy_address = deployment_info.get("proxy")

        # Return both addresses for clarity
        if proxy_address and implementation_address:
            return implementation_address  # Return implementation for the API, but note proxy is used for calls
        elif implementation_address:
            return implementation_address
        else:
            raise ValueError(f"Contract address not found for {contract_name}")

    except Exception as e:
        # Fallback to getting from contract instance
        contract = get_contract(contract_name)
        return contract.address


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