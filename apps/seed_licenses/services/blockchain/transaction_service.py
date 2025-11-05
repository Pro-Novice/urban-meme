import os ,ast,json, logging, binascii
from typing import Any, List, Dict, Optional
from web3.exceptions import ContractLogicError
from celery import shared_task
from web3 import Web3
from hexbytes import HexBytes
from django.conf import settings

from .connection import w3, NONCE_LOCK, get_default_account
from .contract_manager import get_contract
from .data_transformer import format_and_transform_response
from .event_parser import EventParser

logger = logging.getLogger(__name__)

_cached_abi = None  


# ================== TRANSACTION SERVICE ================== #
class TransactionService:
    """
    Handles all blockchain read/write transactions for the License contract.
    Provides:
        - Safe concurrent writes (nonce locking)
        - Smart error parsing
        - Rich block + transaction introspection
    """

    def __init__(self, contract=None):
        self.contract = contract or get_contract()
        self.abi = self.contract.abi
        self.address = self.contract.address

    # --------------------- READ --------------------- #
    def read(self, method_name: str, params: List[Any]) -> Any:
        """Executes a read-only (view/pure) smart contract method."""
        try:
            if not hasattr(self.contract.functions, method_name):
                raise ValueError(f"Method '{method_name}' not found in contract ABI")

            func = getattr(self.contract.functions, method_name)
            result = func(*params).call()

            return format_and_transform_response(result, method_name, self.contract)

        except ContractLogicError as e:
            logger.error(f"Contract logic error in {method_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading from contract ({method_name}): {e}")
            raise

    # --------------------- WRITE --------------------- #
    def write(
        self,
        method_name: str,
        params: List[Any],
        address: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a state-changing (write) smart contract transaction.
        Handles nonce locking, signing, and async confirmation.
        """
        try:
            if not hasattr(self.contract.functions, method_name):
                available = [f["name"] for f in self.abi if f.get("type") == "function"]
                return {
                    "success": False,
                    "error": f"Method '{method_name}' not found",
                    "available_methods": available,
                }

            creds = self._resolve_credentials(address, private_key)
            func = getattr(self.contract.functions, method_name)

            # Thread-safe nonce access
            with NONCE_LOCK:
                nonce = w3.eth.get_transaction_count(creds["address"], "pending")
                tx = func(*params).build_transaction({
                    "from": creds["address"],
                    "gasPrice": w3.eth.gas_price,
                    "nonce": nonce,
                    "chainId": w3.eth.chain_id,
                })

                gas_estimate = w3.eth.estimate_gas(tx)
                tx["gas"] = int(gas_estimate * 1.2)  # add safety buffer

                signed = w3.eth.account.sign_transaction(tx, creds["private_key"])
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            tx_hash_hex = tx_hash.hex()

            # Async background event confirmation
            process_transaction_confirmation.delay(tx_hash_hex, self.abi, self.address)

            return {
                "success": True,
                "transaction_hash": tx_hash_hex,
                "status": "pending",
                "message": "Transaction submitted successfully. Check status later.",
            }

        except Exception as e:
            return self._parse_error(e)

    # --------------------- STATUS --------------------- #
    def get_status(self, tx_hash: str) -> Dict[str, Any]:
        """Fetches transaction confirmation and meta info."""
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

    # --------------------- BLOCK INSPECTION --------------------- #
    def get_block_with_transactions(self, block_number: int) -> dict:
        """
        Fetch complete block info with all transactions and decoded details.
        Converts all HexBytes for JSON serialization.
        """
        def to_hex(value):
            if isinstance(value, (HexBytes, bytes)):
                return value.hex()
            return value

        def load_contract_abi():
            """
            Load ABI from CONTRACT_ABI_PATH.
            Supports both Hardhat artifact and deployment_info.json structure.
            Caches ABI in memory for performance.
            """
            global _cached_abi
            if _cached_abi:
                return _cached_abi

            abi_path = getattr(settings, "CONTRACT_ABI_PATH", None)
            if not abi_path or not os.path.exists(abi_path):
                logger.warning(f"[Decode] ABI file missing at {abi_path}")
                return None

            try:
                with open(abi_path, "r") as f:
                    abi_data = json.load(f)

                # ✅ Case 1: Hardhat artifact or raw ABI
                if isinstance(abi_data, list):
                    _cached_abi = abi_data
                    return _cached_abi

                if isinstance(abi_data, dict):
                    # ✅ Case 2: Hardhat artifact format
                    if "abi" in abi_data:
                        _cached_abi = abi_data["abi"]
                        return _cached_abi

                    # ✅ Case 3: deployment_info.json structure
                    current_impl = abi_data.get("currentImplementation", "V1")
                    impls = abi_data.get("implementations", {})
                    if current_impl in impls and "abi" in impls[current_impl]:
                        _cached_abi = impls[current_impl]["abi"]
                        return _cached_abi

                logger.warning(f"[Decode] Invalid ABI format at {abi_path}")
                return None

            except Exception as e:
                logger.warning(f"[Decode] Failed to load ABI from {abi_path}: {e}")
                return None


        def safe_decode_input(tx_input, to_addr):
            """
            Decode smart contract call input using cached ABI.
            Safely handles decode errors and malformed ABI formats.
            """
            try:
                if not tx_input or tx_input == "0x" or not to_addr:
                    return None

                abi = load_contract_abi()
                if not abi:
                    return None

                contract = Web3().eth.contract(address=to_addr, abi=abi)
                func_obj, params = contract.decode_function_input(tx_input)

                return {"function": func_obj.fn_name, "params": params}

            except Exception as e:
                try:
                    error_text = str(e)
                except Exception:
                    error_text = repr(e)

                selector = tx_input[:10] if len(tx_input) >= 10 else tx_input
                logger.debug(f"[Decode] Failed for {to_addr} (selector={selector}): {error_text}")
                return None

        def extract_logs(tx_hash):
            """Fetch and format transaction logs."""
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                logs = []
                for log in receipt.logs:
                    logs.append({
                        "address": log["address"],
                        "topics": [t.hex() for t in log["topics"]],
                        "data": log["data"],
                    })
                return logs
            except Exception as e:
                logger.debug(f"Log extraction failed for {tx_hash}: {e}")
                return []

        try:
            block = w3.eth.get_block(block_number, full_transactions=True)

            block_info = {
                "block_number": block.number,
                "block_hash": to_hex(block.hash),
                "parent_hash": to_hex(block.parentHash),
                "miner": block.miner,
                "timestamp": block.timestamp,
                "gas_used": block.gasUsed,
                "gas_limit": block.gasLimit,
                "transaction_count": len(block.transactions),
                "transactions": [],
            }

            for tx in block.transactions:
                decoded_input = safe_decode_input(to_hex(tx["input"]), tx["to"])
                logs = extract_logs(to_hex(tx.hash))

                tx_info = {
                    "hash": to_hex(tx.hash),
                    "from": tx["from"],
                    "to": tx["to"],
                    "value_wei": tx["value"],
                    "value_eth": float(w3.from_wei(tx["value"], "ether")),
                    "gas": tx["gas"],
                    "gas_price_gwei": float(w3.from_wei(tx["gasPrice"], "gwei")),
                    "nonce": tx["nonce"],
                    "input": to_hex(tx["input"]),
                    "decoded_input": decoded_input,
                    "logs": logs,
                }
                block_info["transactions"].append(tx_info)

            return {"success": True, "data": block_info}

        except Exception as e:
            logger.error(f"Block fetch error for {block_number}: {e}")
            return {"success": False, "error": str(e)}

    # --------------------- HELPERS --------------------- #
    def _resolve_credentials(self, address, private_key):
        """Resolves credentials from args or env default."""
        if address and private_key:
            return {"address": address, "private_key": private_key}
        default = get_default_account()
        if not default:
            raise ValueError("No credentials provided and no default PRIVATE_KEY configured.")
        return default

    def _parse_error(self, e: Exception) -> Dict[str, Any]:
        """Formats revert or RPC error for human readability."""
        try:
            error_details_str = str(e.args[0])
            error_dict = ast.literal_eval(error_details_str)
            revert_reason = error_dict.get("message", "Execution reverted without reason")
            return {"success": False, "error": revert_reason}
        except Exception:
            return {"success": False, "error": str(e)}


# ================== ASYNC CONFIRMATION ================== #
@shared_task
def process_transaction_confirmation(tx_hash: str, abi: List[Dict], contract_address: str):
    """
    Celery background task:
    Waits for transaction confirmation, parses events, and persists results.
    """
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        parser = EventParser(abi, contract_address)
        license_id, events = parser.parse_and_store(receipt)
        logger.info(f"Transaction {tx_hash} confirmed. Parsed {len(events)} events.")
    except Exception as e:
        logger.error(f"Error processing transaction {tx_hash}: {e}")
