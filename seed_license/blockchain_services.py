import json, logging, os
from django.conf import settings
from web3 import Web3

from web3.exceptions import ContractLogicError
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)


class POAWeb3(Web3):
    def __init__(self, provider=None):
        super().__init__(provider)

        # This is a simplified patch to ignore extraData validation
        # It works by overriding the get_block method
        original_get_block = self.eth.get_block

        def patched_get_block(block_identifier, full_transactions=False):
            try:
                return original_get_block(block_identifier, full_transactions)
            except Exception as e:
                if 'extraData' in str(e):
                    # Log the error but continue
                    import logging
                    logging.warning(f"Ignored extraData error for block {block_identifier}")

                    # For timestamp, return a dummy block with current time if needed
                    from datetime import datetime
                    import time

                    class DummyBlock:
                        pass

                    dummy = DummyBlock()
                    dummy.timestamp = int(time.time())
                    return dummy
                else:
                    # Re-raise if it's not an extraData error
                    raise

        # Replace the method
        self.eth.get_block = patched_get_block
# ── connect ───────────────────────────────────────────────────────────
w3 =POAWeb3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL))
if not w3.is_connected():
    raise ConnectionError("Cannot connect to blockchain node")


DEFAULT_PRIVATE_KEY = settings.PRIVATE_KEY
if not DEFAULT_PRIVATE_KEY:
    raise RuntimeError("settings.PRIVATE_KEY is missing – add it to .env")
DEFAULT_ACCOUNT = w3.eth.account.from_key(DEFAULT_PRIVATE_KEY)
DEFAULT_ADDRESS = DEFAULT_ACCOUNT.address



BASE_DIR = settings.BASE_DIR
CONTRACTS_DIR = os.path.join(BASE_DIR, "Services", "blockchain", "contracts")


def get_contract(contract_name: str):
    """Load ABI + address and return web3 Contract."""
    try:
        abi_path = os.path.join(CONTRACTS_DIR, "abi", "seedLicenseContract.json")
        addr_path = os.path.join(CONTRACTS_DIR, "contract_address", "addresses.txt")
        
        with open(abi_path, "r") as fh:
            abi = json.load(fh)
        with open(addr_path, "r") as fh:
            addresses = json.load(fh)
        contract_address = addresses.get(contract_name)
        if not contract_address:
            raise ValueError(f"Contract address not found for {contract_name}")
        return w3.eth.contract(address=contract_address, abi=abi)
    except Exception as exc:
        logger.error("Contract loading error: %s", exc)
        raise


def _sign_and_send(tx: dict, private_key: str) -> str:
    signed = w3.eth.account.sign_transaction(tx, private_key)
    return w3.eth.send_raw_transaction(signed.raw_transaction)


def call_function(function, *args, address=None, private_key=None):
    """Build, sign & send a state‑changing transaction and wait for receipt."""
    sender = address or DEFAULT_ADDRESS
    key    = private_key or DEFAULT_PRIVATE_KEY

    tx = function(*args).build_transaction({
        "from":     sender,
        "nonce":    w3.eth.get_transaction_count(sender),
        "gasPrice": w3.eth.gas_price,
    })
    tx["gas"] = w3.eth.estimate_gas(tx)

    tx_hash = _sign_and_send(tx, key)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def call_view_function(function, *args):
    """Read‑only contract call."""
    return function(*args).call()


def get_transaction_status(tx_hash: str):
    """Return Tx status + meta used by `/blockchain/transactions/*` APIs."""
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        block   = w3.eth.get_block(receipt.blockNumber)
        return {
            "tx_hash":       tx_hash,
            "status":        "CONFIRMED" if receipt.status == 1 else "FAILED",
            "block_number":  receipt.blockNumber,
            "timestamp":     block.timestamp,
            "confirmations": w3.eth.block_number - receipt.blockNumber,
        }
    except Exception as exc:
        return {"tx_hash": tx_hash, "status": "PENDING", "error": str(exc)}