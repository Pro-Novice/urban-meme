import logging
import json
import os
from web3 import Web3
from web3.exceptions import ContractLogicError
# from web3.middleware.geth_poa import geth_poa_middleware
from django.conf import settings

logger = logging.getLogger(__name__)

w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL))
# w3.middleware_onion.inject(geth_poa_middleware, layer=0)

def connect_to_blockchain():
    if not w3.is_connected():
        raise ConnectionError("Cannot connect to blockchain node")
    return w3

def get_contract(contract_name):
    try:
        ABI_PATH = os.path.abspath(os.path.join(
            "Services", "blockchain", "contracts", "abi", "seedLicenseContract.json"
        ))
        ADDRESS_PATH = os.path.abspath(os.path.join(
            "Services", "blockchain", "contracts", "contract_address", "addresses.txt"
        ))

        with open(ABI_PATH, 'r') as abi_file:
            abi = json.load(abi_file)

        with open(ADDRESS_PATH, 'r') as addr_file:
            addresses = json.load(addr_file)
            contract_address = addresses.get(contract_name)

        if not contract_address:
            raise ValueError(f"Contract address not found for {contract_name}")

        return w3.eth.contract(address=contract_address, abi=abi)

    except Exception as e:
        logger.error(f"Contract loading error: {e}")
        raise

def call_function(function, *args, address=None, private_key=None):
    if not address:
        raise ValueError("Sender address is required")

    try:
        tx = function(*args).build_transaction({
            'from': address,
            'nonce': w3.eth.get_transaction_count(address),
            'gasPrice': w3.eth.gas_price
        })

        tx['gas'] = w3.eth.estimate_gas(tx)

        if private_key:
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            return w3.eth.wait_for_transaction_receipt(tx_hash)

        return tx

    except Exception as e:
        logger.error(f"Error in call_function: {e}")
        raise

def call_view_function(function, *args):
    try:
        return function(*args).call()
    except Exception as e:
        logger.error(f"Error in call_view_function: {e}")
        raise

def get_transaction_status(tx_hash):
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        tx = w3.eth.get_transaction(tx_hash)
        return {
            "tx_hash": tx_hash,
            "status": "CONFIRMED" if receipt.status == 1 else "FAILED",
            "block_number": receipt.blockNumber,
            "timestamp": w3.eth.get_block(receipt.blockNumber).timestamp,
            "confirmations": w3.eth.block_number - receipt.blockNumber
        }
    except Exception as e:
        return {"tx_hash": tx_hash, "status": "PENDING", "error": str(e)}
