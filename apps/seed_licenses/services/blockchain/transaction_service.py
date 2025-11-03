import ast
import logging
from typing import Any, List, Dict, Optional
from web3.exceptions import ContractLogicError
from .connection import w3, NONCE_LOCK, get_default_account
from .contract_manager import get_contract
from .data_transformer import format_and_transform_response
from .event_parser import EventParser
from celery import shared_task

logger = logging.getLogger(__name__)


# ================== TRANSACTION SERVICE ================== #
class TransactionService:
    """
    Handles all blockchain read/write transactions for the License contract.
    """

    def __init__(self, contract=None):
        self.contract = contract or get_contract()
        self.abi = self.contract.abi
        self.address = self.contract.address

    # --------------------- READ --------------------- #
    def read(self, method_name: str, params: List[Any]) -> Any:
        """
        Executes a read-only (view/pure) smart contract method.
        """
        try:
            if not hasattr(self.contract.functions, method_name):
                raise ValueError(f"Method '{method_name}' not found in contract ABI")

            contract_function = getattr(self.contract.functions, method_name)
            result = contract_function(*params).call()

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
            # Get contract function
            if not hasattr(self.contract.functions, method_name):
                available = [f["name"] for f in self.abi if f.get("type") == "function"]
                return {
                    "success": False,
                    "error": f"Method '{method_name}' not found",
                    "available_methods": available,
                }

            # Load credentials
            creds = self._resolve_credentials(address, private_key)
            func = getattr(self.contract.functions, method_name)

            # Thread-safe transaction section
            with NONCE_LOCK:
                nonce = w3.eth.get_transaction_count(creds["address"], "pending")

                tx = func(*params).build_transaction({
                    "from": creds["address"],
                    "gasPrice": w3.eth.gas_price,
                    "nonce": nonce,
                    "chainId": w3.eth.chain_id,
                })

                # Gas estimation with 20% buffer
                gas_estimate = w3.eth.estimate_gas(tx)
                tx["gas"] = int(gas_estimate * 1.2)

                # Sign and send transaction
                signed = w3.eth.account.sign_transaction(tx, creds["private_key"])
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            tx_hash_hex = tx_hash.hex()

            # Trigger async confirmation
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
        """
        Fetches transaction confirmation and meta info.
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
        except Exception as e:
            return {"tx_hash": tx_hash, "status": "PENDING", "error": str(e)}

    # --------------------- HELPERS --------------------- #
    def _resolve_credentials(self, address, private_key):
        """Resolves credentials either from provided args or default account."""
        if address and private_key:
            return {"address": address, "private_key": private_key}
        default = get_default_account()
        if not default:
            raise ValueError("No credentials provided and no default PRIVATE_KEY configured.")
        return default

    def _parse_error(self, e: Exception) -> Dict[str, Any]:
        """Parses revert or execution errors into readable dicts."""
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
    Waits for transaction confirmation, parses events, and saves them to DB.
    """
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        parser = EventParser(abi, contract_address)
        license_id, events = parser.parse_and_store(receipt)
        logger.info(f"Transaction {tx_hash} confirmed. Parsed {len(events)} events.")
    except Exception as e:
        logger.error(f"Error processing transaction {tx_hash}: {e}")
