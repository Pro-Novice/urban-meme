import json, logging, os
from typing import Any, List, Dict, Union, Optional, Tuple
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
        abi = None
        
        # For LicenseSystemV1, we need to check if there's an implementation ABI file
        if contract_name in ["LicenseSystemV1", "seedLicenseContract"]:
            # Look for the implementation ABI that was shown in your screenshot
            possible_abi_locations = [
                # Check in blockchainDeploymentScripts folder
                os.path.join(BASE_DIR, "blockchainDeploymentScripts", "implementationABI", "LicenseSystemV1.json"),
                os.path.join(BASE_DIR, "blockchainDeploymentScripts", "LicenseSystemV1ImplementationABI.json"),
                os.path.join(BASE_DIR, "blockchainDeploymentScripts", "[ ] implementationABI.json"),
                # Check in standard locations
                os.path.join(CONTRACTS_DIR, "abi", "LicenseSystemV1.json"),
                os.path.join(CONTRACTS_DIR, "abi", "seedLicenseContract.json"),
            ]
            
            # Try each location
            for abi_path in possible_abi_locations:
                if os.path.exists(abi_path):
                    with open(abi_path, "r") as fh:
                        abi = json.load(fh)
                    logger.info(f"Found ABI at: {abi_path}")
                    abi_found = True
                    break
        
        # If no ABI found yet, check if it's the other contract type
        if not abi_found:
            # This might be the seed license tracking contract
            seed_abi_path = os.path.join(CONTRACTS_DIR, "abi", "seedLicenseContract.json")
            if os.path.exists(seed_abi_path):
                with open(seed_abi_path, "r") as fh:
                    abi = json.load(fh)
                logger.info(f"Using seed license ABI from: {seed_abi_path}")
                abi_found = True
        
        if not abi_found or not abi:
            # List available files for debugging
            logger.error(f"Could not find ABI for {contract_name}")
            logger.error(f"Checked locations: {possible_abi_locations if 'possible_abi_locations' in locals() else 'N/A'}")
            
            # Try to list what files are available
            deployment_dir = os.path.join(BASE_DIR, "blockchainDeploymentScripts")
            if os.path.exists(deployment_dir):
                files = os.listdir(deployment_dir)
                logger.error(f"Files in deployment directory: {files}")
            
            raise FileNotFoundError(f"No ABI file found for {contract_name}")
        
        # Create contract instance with PROXY address and IMPLEMENTATION ABI
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), 
            abi=abi
        )
        
        # Cache the contract
        _contract_cache[contract_name] = contract
        
        logger.info(f"Contract {contract_name} loaded successfully with proxy address: {contract_address}")
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


def extract_license_id_from_events(events: List[Dict[str, Any]], method_name: str) -> Optional[int]:
    """
    Extract license ID from events based on the method called
    """
    try:
        if method_name == "applyForLicense":
            for event in events:
                if event.get("event") == "LicenseApplied" and "license_id" in event:
                    return event["license_id"]
        elif method_name == "updateLicenseStatus":
            for event in events:
                if event.get("event") == "LicenseStatusUpdated" and "license_id" in event:
                    return event["license_id"]
        elif method_name in ["revokeLicense"]:  # If you have this method
            for event in events:
                if event.get("event") == "LicenseRevoked" and "license_id" in event:
                    return event["license_id"]
    except Exception as e:
        logger.warning(f"Could not extract license ID from events: {e}")
    
    return None


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
    Universal function to write to any smart contract method
    Enhanced to capture return values and license IDs
    """
    try:
        # =============== NETWORK DEBUGGING INFORMATION ===============
        logger.info(f"🌐 NETWORK CONNECTION DEBUG:")
        logger.info(f"   RPC URL: {w3.provider.endpoint_uri}")
        
        try:
            chain_id = w3.eth.chain_id
            latest_block = w3.eth.block_number
            logger.info(f"   Chain ID: {chain_id}")
            logger.info(f"   Latest block: {latest_block}")
            
            # Map chain IDs to network names
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
            network_name = network_names.get(chain_id, f"Unknown Network (ID: {chain_id})")
            logger.info(f"   Network: {network_name}")
            
            # Check if connected properly
            if not w3.is_connected():
                logger.error(f"❌ Web3 connection failed!")
            else:
                logger.info(f"✅ Web3 connected successfully")
                
        except Exception as net_error:
            logger.error(f"❌ Failed to get network info: {net_error}")
        
        # =============== ACCOUNT BALANCE CHECK ===============
        sender_address = address or DEFAULT_ADDRESS
        try:
            balance_wei = w3.eth.get_balance(sender_address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            logger.info(f"💰 Account balance check:")
            logger.info(f"   Address: {sender_address}")
            logger.info(f"   Balance: {balance_eth:.6f} ETH")
            
            if balance_eth < 0.001:
                logger.warning(f"⚠️ Low balance detected: {balance_eth:.6f} ETH")
                
        except Exception as balance_error:
            logger.error(f"❌ Failed to check account balance: {balance_error}")
        
        # =============== CONTRACT INFORMATION ===============
        contract = get_contract(contract_name)
        
        logger.info(f"📋 CONTRACT DEBUG:")
        logger.info(f"   Contract name: {contract_name}")
        logger.info(f"   Contract address: {contract.address}")
        logger.info(f"   Method: {method_name}")
        logger.info(f"   Params: {params}")
        logger.info(f"   From address: {sender_address}")
        
        # Check if method exists
        if not hasattr(contract.functions, method_name):
            raise ValueError(f"Method '{method_name}' not found in contract '{contract_name}'")
        
        # Get the function
        contract_function = getattr(contract.functions, method_name)
        
        # Process parameters
        processed_params = process_params_for_abi(params, contract_function, contract)
        logger.info(f"   Processed params: {processed_params}")
        
        # =============== GAS ESTIMATION DEBUG ===============
        try:
            # Build a test transaction for gas estimation
            test_tx = contract_function(*processed_params).build_transaction({
                'from': sender_address,
                'nonce': w3.eth.get_transaction_count(sender_address, 'pending'),
                'gasPrice': w3.eth.gas_price,
            })
            
            # Estimate gas
            estimated_gas = w3.eth.estimate_gas(test_tx)
            gas_price = w3.eth.gas_price
            estimated_cost_wei = estimated_gas * gas_price
            estimated_cost_eth = w3.from_wei(estimated_cost_wei, 'ether')
            
            logger.info(f"⛽ GAS ESTIMATION:")
            logger.info(f"   Estimated gas: {estimated_gas:,}")
            logger.info(f"   Gas price: {w3.from_wei(gas_price, 'gwei')} gwei")
            logger.info(f"   Estimated cost: {estimated_cost_eth:.6f} ETH")
            
            # Check if account can afford the transaction
            balance_wei = w3.eth.get_balance(sender_address)
            if estimated_cost_wei > balance_wei:
                logger.error(f"❌ INSUFFICIENT FUNDS:")
                logger.error(f"   Need: {estimated_cost_eth:.6f} ETH")
                logger.error(f"   Have: {w3.from_wei(balance_wei, 'ether'):.6f} ETH")
                logger.error(f"   Shortfall: {w3.from_wei(estimated_cost_wei - balance_wei, 'ether'):.6f} ETH")
                
        except Exception as gas_error:
            logger.error(f"❌ Gas estimation failed: {gas_error}")
        
        # =============== EXECUTE TRANSACTION ===============
        logger.info(f"🚀 Executing transaction...")
        
        # Call the function - NOW RETURNS BOTH RECEIPT AND RETURN VALUE
        receipt, return_value = call_function(contract_function, *processed_params, address=address, private_key=private_key)
        
        # Parse events from receipt
        events = parse_receipt_events(receipt, contract)
        
        logger.info(f"✅ Transaction completed:")
        logger.info(f"   Status: {'Success' if receipt.status == 1 else 'Failed'}")
        logger.info(f"   Transaction hash: {receipt.transactionHash.hex()}")
        logger.info(f"   Block number: {receipt.blockNumber}")
        logger.info(f"   Gas used: {receipt.gasUsed:,}")
        if return_value is not None:
            logger.info(f"   Return value: {return_value}")
        
        # =============== BUILD RESPONSE ===============
        response = {
            "success": receipt.status == 1,
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "events": events,
            "status": "confirmed" if receipt.status == 1 else "failed",
            "network_info": {
                "rpc_url": str(w3.provider.endpoint_uri),
                "chain_id": w3.eth.chain_id,
                "network_name": network_names.get(w3.eth.chain_id, f"Unknown (ID: {w3.eth.chain_id})"),
                "sender_address": sender_address
            }
        }
        
        # =============== ADD RETURN VALUE IF PRESENT ===============
        if return_value is not None:
            response["return_value"] = return_value
            
            # For specific methods, add convenience fields
            if method_name == "applyForLicense" and isinstance(return_value, int):
                response["license_id"] = return_value
                logger.info(f"📋 License created with ID: {return_value}")
        
        # =============== EXTRACT LICENSE ID FROM EVENTS ===============
        # If no return value, try to get license ID from events
        if "license_id" not in response:
            event_license_id = extract_license_id_from_events(events, method_name)
            if event_license_id is not None:
                response["license_id"] = event_license_id
                logger.info(f"📋 License ID extracted from events: {event_license_id}")
        
        # =============== ADD ADDITIONAL METADATA ===============
        if method_name == "applyForLicense":
            response["message"] = "License application submitted successfully"
            if "license_id" in response:
                response["message"] += f" with ID: {response['license_id']}"
        elif method_name == "updateLicenseStatus":
            response["message"] = "License status updated successfully"
        elif method_name == "addDepartmentOfficer":
            response["message"] = "Department officer added successfully"
        elif method_name == "removeDepartmentOfficer":
            response["message"] = "Department officer removed successfully"
            
        response["receipt"] = {
            "transactionHash": receipt.transactionHash.hex(),
            "blockHash": receipt.blockHash.hex(),
            "blockNumber": receipt.blockNumber,
            "from": receipt["from"],
            "to": receipt["to"],
            "gasUsed": receipt.gasUsed,
            "cumulativeGasUsed": receipt.cumulativeGasUsed,
            "status": receipt.status,
            "contractAddress": receipt.contractAddress,
            "logs": [dict(log) for log in receipt.logs],
            "type": receipt.type,
            "effectiveGasPrice": receipt.effectiveGasPrice,
            "transactionIndex": receipt.transactionIndex
        }
        return response
        
    except ContractLogicError as e:
        error_msg = str(e)
        logger.error(f"Contract logic error: {error_msg}")
        
        # Parse common contract revert reasons
        if "Contract reverted" in error_msg:
            if "Only admin" in error_msg:
                return {
                    "success": False,
                    "error": "Permission denied: Only admin can perform this action",
                    "details": "The calling address does not have admin privileges",
                    "solution": "Ensure you're using the admin address or grant admin role to your address",
                    "network_info": _get_network_info()
                }
            elif "Already exists" in error_msg:
                return {
                    "success": False,
                    "error": "License already exists",
                    "details": "A license with similar details may already exist",
                    "solution": "Check if the farmer already has an active license",
                    "network_info": _get_network_info()
                }
            elif "Invalid status" in error_msg:
                return {
                    "success": False,
                    "error": "Invalid license status transition",
                    "details": "The requested status change is not allowed from current status",
                    "solution": "Check the current license status and valid transitions",
                    "network_info": _get_network_info()
                }
            elif "not found" in error_msg or "Does not exist" in error_msg:
                return {
                    "success": False,
                    "error": "License not found",
                    "details": "The specified license ID does not exist",
                    "solution": "Verify the license ID is correct",
                    "network_info": _get_network_info()
                }
        
        # Generic contract revert
        return {
            "success": False,
            "error": "Smart contract execution failed",
            "details": error_msg,
            "solution": "Check contract requirements and ensure all conditions are met",
            "network_info": _get_network_info()
        }
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Value error: {error_msg}")
        
        if "Method" in error_msg and "not found" in error_msg:
            return {
                "success": False,
                "error": f"Method '{method_name}' does not exist in contract",
                "details": "The specified method name is not available in the contract ABI",
                "solution": f"Check available methods at /api/seed-license/blockchain/contracts/{contract_name}/methods/",
                "network_info": _get_network_info()
            }
        elif "Contract files not found" in error_msg:
            return {
                "success": False,
                "error": "Contract configuration not found",
                "details": f"Unable to load ABI or address for contract '{contract_name}'",
                "solution": "Ensure the contract is properly deployed and configuration files exist",
                "network_info": _get_network_info()
            }
            
        return {
            "success": False,
            "error": "Invalid request parameters",
            "details": error_msg,
            "solution": "Verify all parameters are correctly formatted",
            "network_info": _get_network_info()
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in write_to_contract: {error_msg}", exc_info=True)
        
        # Parse specific Web3 errors
        if "insufficient funds" in error_msg.lower():
            return {
                "success": False,
                "error": "Insufficient funds for transaction",
                "details": "The sending address does not have enough ETH to pay for gas",
                "solution": "Add ETH to the sending address",
                "sending_address": address or DEFAULT_ADDRESS,
                "network_info": _get_network_info()
            }
        elif "nonce too low" in error_msg.lower():
            return {
                "success": False,
                "error": "Transaction nonce error",
                "details": "The transaction nonce is too low",
                "solution": "Wait for pending transactions to complete or reset the nonce",
                "network_info": _get_network_info()
            }
        elif "execution reverted" in error_msg and "no data" in error_msg:
            return {
                "success": False,
                "error": "Contract execution reverted without reason",
                "details": "The contract reverted but didn't provide a specific error message",
                "possible_causes": [
                    "Contract may not be initialized",
                    "Sender may lack required permissions",
                    "Input parameters may be invalid",
                    "Contract state may prevent this operation"
                ],
                "debugging_steps": [
                    "1. Check if contract is initialized (if upgradeable)",
                    "2. Verify sender has necessary roles/permissions",
                    "3. Ensure all parameters match expected types",
                    "4. Check contract's current state"
                ],
                "contract_address": getattr(contract, 'address', 'unknown'),
                "method": method_name,
                "sender": address or DEFAULT_ADDRESS,
                "network_info": _get_network_info()
            }
        elif "connection" in error_msg.lower() or "provider" in error_msg.lower():
            return {
                "success": False,
                "error": "Blockchain connection error",
                "details": "Unable to connect to the blockchain node",
                "solution": "Check blockchain node URL and network connectivity",
                "network_info": _get_network_info()
            }
            
        # Generic error
        return {
            "success": False,
            "error": "Transaction failed",
            "details": error_msg,
            "solution": "Check logs for more detailed error information",
            "network_info": _get_network_info()
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