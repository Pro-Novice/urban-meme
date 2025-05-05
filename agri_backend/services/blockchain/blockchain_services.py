import logging
import json
import os
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.middleware import geth_poa_middleware
from django.conf import settings

logger = logging.getLogger(__name__)

# Initialize Web3 connection
w3 = Web3(Web3.HTTPProvider(f"http://{settings.BLOCKCHAIN_HOST}:{settings.BLOCKCHAIN_PORT}"))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

def connect_to_blockchain():
    """Ensure blockchain connection is active"""
    if not w3.is_connected():
        raise ConnectionError("Cannot connect to blockchain node")
    return w3

def get_contract(contract_name):
    """Get contract instance"""
    try:
        # Get absolute path to ABI file
        ABI_PATH = os.path.abspath(os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "abi.txt"
        ))
        
        with open(ABI_PATH, 'r') as abi_file:
            abi = json.load(abi_file)
                
        # Load contract address - ensure path is correct
        ADDRESS_PATH = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "..",
            "blockchain",
            "contracts",
            "contract_address",
            "addresses.txt"
        ))
        
        with open(ADDRESS_PATH, 'r') as f:
            addresses = json.load(f)
            contract_address = addresses.get(contract_name)
        
        if not contract_address:
            raise ValueError(f"Contract address not found for {contract_name}")
        
        return w3.eth.contract(address=contract_address, abi=abi)
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format in file: {str(e)}")
        raise
    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error getting contract {contract_name}: {str(e)}")
        raise

def call_function(function, *args, address=None, private_key=None):
    """Call a contract function that modifies state"""
    if not address:
        raise ValueError("Sender address is required")
    
    try:
        # Build transaction
        tx = function(*args).build_transaction({
            'from': address,
            'nonce': w3.eth.get_transaction_count(address),
            'gasPrice': w3.eth.gas_price
        })
        
        # Add gas estimation
        tx['gas'] = w3.eth.estimate_gas(tx)
        
        # Sign and send transaction
        if private_key:
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            return w3.eth.wait_for_transaction_receipt(tx_hash)  # Updated method
        return tx
    
    except ContractLogicError as e:
        logger.error(f"Contract logic error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error calling function: {str(e)}")
        raise

def call_view_function(function, *args):
    """Call a contract view function"""
    try:
        return function(*args).call()
    except ContractLogicError as e:
        logger.error(f"Contract logic error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error calling view function: {str(e)}")
        raise