import os, ast, json, logging, binascii, asyncio
from typing import Any, List, Dict, Optional
from web3 import Web3
from web3.exceptions import ContractLogicError
from hexbytes import HexBytes
from celery import shared_task
from django.conf import settings
from .connection import multi_rpc as rpc_manager, w3, NONCE_LOCK, get_default_account
from .contract_manager import get_contract
from .data_transformer import format_and_transform_response
from .event_parser import EventParser

logger = logging.getLogger(__name__)

_cached_abi = None


# ======================================================
# TRANSACTION SERVICE
# ======================================================
class TransactionService:
    """
    Blockchain read/write service for the License contract.
    Integrates async MultiRPCWeb3 load-balanced RPC layer.
    """

    def __init__(self, contract=None):
        self.contract = contract or get_contract()
        self.abi = self.contract.abi
        self.address = self.contract.address

    # ------------------------------------------------------
    # READ (SYNC)
    # ------------------------------------------------------
    def read(self, method_name: str, params: List[Any]) -> Any:
        """Read-only contract call (view/pure)."""
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

    # ------------------------------------------------------
    # WRITE (STATE-CHANGING TX)
    # ------------------------------------------------------
    def write(
        self,
        method_name: str,
        params: List[Any],
        address: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a transaction to the contract.
        Uses thread-safe nonce locking (per address), async confirmation,
        and MultiRPCWeb3 load-balancing.
        """
        try:
            #  Validate method existence
            if not hasattr(self.contract.functions, method_name):
                available = [f["name"] for f in self.abi if f.get("type") == "function"]
                return {
                    "success": False,
                    "error": f"Method '{method_name}' not found",
                    "available_methods": available,
                }

            creds = self._resolve_credentials(address, private_key)
            func = getattr(self.contract.functions, method_name)

            # ------------------------------------------------------------
            #  Lock only for nonce fetching to prevent race conditions
            # ------------------------------------------------------------
            if not hasattr(self, "_nonce_locks"):
                from collections import defaultdict
                import threading
                self._nonce_locks = defaultdict(threading.Lock)

            with self._nonce_locks[creds["address"]]:
                nonce = w3.eth.get_transaction_count(creds["address"], "pending")

            # ------------------------------------------------------------
            #  Build and sign transaction OUTSIDE the lock
            # ------------------------------------------------------------
            tx = func(*params).build_transaction({
                "from": creds["address"],
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
                "chainId": w3.eth.chain_id,
            })

            gas_estimate = w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.2)

            signed_tx = w3.eth.account.sign_transaction(tx, creds["private_key"])

            # ------------------------------------------------------------
            #  Async RPC send (with fallback to sync)
            # ------------------------------------------------------------
            async def _send_async(raw_tx):
                try:
                    result = await rpc_manager.call("eth_sendRawTransaction", [raw_tx.hex()])
                    return result.get("result")
                except Exception as e:
                    logger.warning(f"[RPC] Fallback send failed: {e}")
                    return w3.eth.send_raw_transaction(raw_tx).hex()

            try:
                tx_hash_hex = asyncio.run(_send_async(signed_tx.raw_transaction))
            except RuntimeError:
                # Handles case when already inside event loop (e.g. Celery)
                tx_hash_hex = asyncio.get_event_loop().run_until_complete(
                    _send_async(signed_tx.raw_transaction)
                )

            # ------------------------------------------------------------
            #  Schedule async confirmation
            # ------------------------------------------------------------
            process_transaction_confirmation.delay(tx_hash_hex, self.abi, self.address)

            return {
                "success": True,
                "transaction_hash": tx_hash_hex,
                "status": "pending",
                "rpc_url": rpc_manager.get_current_url(),
                "message": "Transaction submitted successfully. Await confirmation.",
            }

        except Exception as e:
            logger.error(f"Transaction error in {method_name}: {e}")
            return self._parse_error(e)


    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------
    def get_status(self, tx_hash: str) -> Dict[str, Any]:
        """Fetch on-chain confirmation and metadata."""
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

    # ------------------------------------------------------
    # BLOCK INSPECTION
    # ------------------------------------------------------
    def get_block_with_transactions(self, block_number: int) -> dict:
        """Fetch full block + tx details, decoding contract calls."""
        def to_hex(value):
            return value.hex() if isinstance(value, (HexBytes, bytes)) else value

        def load_contract_abi():
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
                if isinstance(abi_data, list):
                    _cached_abi = abi_data
                    return _cached_abi
                if isinstance(abi_data, dict):
                    if "abi" in abi_data:
                        _cached_abi = abi_data["abi"]
                        return _cached_abi
                    current_impl = abi_data.get("currentImplementation", "V1")
                    impls = abi_data.get("implementations", {})
                    if current_impl in impls and "abi" in impls[current_impl]:
                        _cached_abi = impls[current_impl]["abi"]
                        return _cached_abi
                logger.warning(f"[Decode] Invalid ABI format at {abi_path}")
                return None
            except Exception as e:
                logger.warning(f"[Decode] Failed to load ABI: {e}")
                return None

        def safe_decode_input(tx_input, to_addr):
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
                selector = tx_input[:10] if len(tx_input) >= 10 else tx_input
                logger.debug(f"[Decode] Failed for {to_addr} (selector={selector}): {e}")
                return None

        def extract_logs(tx_hash):
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

    # ------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------
    def _resolve_credentials(self, address, private_key):
        if address and private_key:
            return {"address": address, "private_key": private_key}
        default = get_default_account()
        if not default:
            raise ValueError("No credentials provided and no default PRIVATE_KEY configured.")
        return default

    def _parse_error(self, e: Exception) -> Dict[str, Any]:
        try:
            error_details_str = str(e.args[0])
            error_dict = ast.literal_eval(error_details_str)
            revert_reason = error_dict.get("message", "Execution reverted without reason")
            return {"success": False, "error": revert_reason}
        except Exception:
            return {"success": False, "error": str(e)}


# ======================================================
# ASYNC CONFIRMATION (CELERY)
# ======================================================
@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_transaction_confirmation(self, tx_hash: str, abi: List[Dict], contract_address: str):
    """
    Celery background task:
    Waits for transaction confirmation using MultiRPCWeb3 async load-balancing.
    Falls back gracefully if RPC nodes disagree or one node lags.
    """
    import asyncio
    from apps.seed_licenses.services.blockchain.connection import rpc_manager

    async def _confirm_transaction(tx_hash: str) -> Optional[Dict]:
        """
        Query all RPC endpoints in parallel until one returns a confirmed receipt.
        Includes timeout protection per node.
        """
        try:
            logger.info(f"[CONFIRM] 🔍 Querying all RPCs for transaction {tx_hash}")

            async def safe_call(url):
                """Send JSON-RPC call safely with timeout."""
                import aiohttp, asyncio
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionReceipt",
                    "params": [tx_hash],
                    "id": 1,
                }
                try:
                    timeout = aiohttp.ClientTimeout(total=8)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(url, json=payload) as resp:
                            return await resp.json()
                except asyncio.TimeoutError:
                    logger.warning(f"[TIMEOUT] RPC {url} timed out for {tx_hash}")
                    return {"error": "timeout"}
                except Exception as e:
                    logger.warning(f"[ERROR] RPC {url} failed for {tx_hash}: {e}")
                    return {"error": str(e)}

            # Launch all requests concurrently
            tasks = [safe_call(url) for url in rpc_manager.rpc_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # logger.info(f"[CONFIRM DEBUG] Received {len(results)} RPC responses for {tx_hash}")
            # for i, res in enumerate(results):
            #     logger.info(f"[CONFIRM DEBUG] RPC[{i}] → {res}")

            # Filter valid receipts
            receipts = [
                r.get("result") for r in results
                if isinstance(r, dict) and r.get("result")
            ]

            if not receipts:
                logger.warning(f"[CONFIRM WARN] No confirmed receipts yet for {tx_hash}")
                return None

            # Return first confirmed one
            for receipt in receipts:
                if receipt.get("blockNumber"):
                    # logger.info(f"[CONFIRM ✅] Found confirmed receipt on node: {receipt}")
                    return receipt

            logger.warning(f"[CONFIRM WARN] No blockNumber found yet for {tx_hash}")
            return None

        except Exception as e:
            logger.warning(f"[CONFIRM ERROR] Async confirmation failed for {tx_hash}: {e}")
            return None

    async def _process_async():
        try:
            logger.info(f"[ASYNC START] Processing transaction confirmation for {tx_hash}")

            # Try up to 20 rounds (≈300s total)
            for attempt in range(20):
                logger.info(f"[ASYNC CHECK] Attempt {attempt+1}/20 for {tx_hash}")
                receipt = await _confirm_transaction(tx_hash)

                if receipt:
                    try:
                        # Normalize receipt block number and status
                        block_number = int(receipt["blockNumber"], 16)
                        tx_status = int(receipt["status"], 16)
                    except Exception:
                        block_number = receipt.get("blockNumber", "?")
                        tx_status = receipt.get("status", "?")

                    logger.info(
                        f"[ASYNC CONFIRMED] ✅ Tx {tx_hash} confirmed "
                        f"on block {block_number} (status={tx_status})"
                    )

                    from types import SimpleNamespace
                    from hexbytes import HexBytes

                    parsed_receipt = SimpleNamespace(
                        blockNumber = block_number,
                        transactionHash=HexBytes(receipt["transactionHash"]),
                        logs=[
                            SimpleNamespace(
                                address=log.get("address"),
                                data=log.get("data"),
                                topics=[HexBytes(t) for t in log.get("topics", [])],
                            )
                            for log in receipt.get("logs", [])
                        ],

                    )

                    # Instantiate parser and store events
                    parser = EventParser(abi, contract_address)
                    logger.info(f"[EVENT PARSER] Starting event parsing for tx={tx_hash}")
                    license_id, events = await parser.parse_and_store(parsed_receipt)

                    logger.info(
                        f"[EVENT PARSER] ✅ Parsed {len(events)} events for license_id={license_id}"
                    )
                    return True

                logger.info(f"[ASYNC WAIT] Tx {tx_hash} not confirmed yet, retrying in 15s...")
                await asyncio.sleep(1)

            logger.warning(f"[TIMEOUT ⚠️] Tx {tx_hash} not confirmed after 5 minutes.")
            return False

        except Exception as e:
            logger.error(f"[ASYNC ERROR] ❌ Error processing tx {tx_hash}: {e}")
            return False

    try:
        logger.info(f"[CELERY TASK] 🚀 Starting async confirmation task for {tx_hash}")
        asyncio.run(_process_async())
    except RuntimeError:
        # If inside an already running loop (Celery async pool)
        loop = asyncio.get_event_loop()
        logger.info(f"[CELERY TASK] 🔁 Using existing event loop for {tx_hash}")
        loop.run_until_complete(_process_async())
