import json, os, logging
from typing import Dict, Tuple
from django.conf import settings
from web3 import Web3
from .connection import w3

logger = logging.getLogger(__name__)

BASE_DIR = settings.BASE_DIR
DEPLOYMENT_INFO_PATH = os.path.join(BASE_DIR, "blockchain", "deployment_info.json")
_contract = None

def load_deployment_info() -> Dict:
    with open(DEPLOYMENT_INFO_PATH, "r") as f:
        return json.load(f)

def get_current_implementation_abi(deployment_info: Dict) -> Tuple[str, Dict]:
    current_version = deployment_info.get("currentImplementation", "V1")
    implementations = deployment_info.get("implementations", {})
    for version in [current_version, "V1"]:
        if version in implementations:
            abi = implementations[version].get("abi")
            if abi:
                return version, abi
    raise FileNotFoundError("No valid ABI found")

def get_contract():
    global _contract
    if _contract:
        return _contract
    deployment_info = load_deployment_info()
    proxy_address = deployment_info.get("proxy")
    version, abi = get_current_implementation_abi(deployment_info)
    _contract = w3.eth.contract(
        address=Web3.to_checksum_address(proxy_address),
        abi=abi
    )
    logger.info(f"Loaded contract {proxy_address} with {version} ABI")
    return _contract
