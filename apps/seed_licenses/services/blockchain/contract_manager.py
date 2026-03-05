import json, os, logging
from typing import Dict, Tuple, List
from django.conf import settings
from web3 import Web3
from .connection import w3
import pprint

logger = logging.getLogger(__name__)

BASE_DIR = settings.BASE_DIR

# Primary & fallback paths
DEPLOYMENT_INFO_PATH = os.path.join(BASE_DIR, "blockchain", "deployment_info.json")
FALLBACK_ABI_PATH = os.path.join(
    BASE_DIR, "blockchain", "artifacts", "contracts", "LicenseSystemV1.sol", "LicenseSystemV1.json"
)

_contract = None


def safe_log(obj):
    """Safely format complex objects for debug logs."""
    try:
        return pprint.pformat(obj, compact=True, width=80)
    except Exception:
        return str(obj)



# ================== LOAD DEPLOYMENT INFO ================== #
def load_json_file(path: str) -> Dict:
    """Safely load JSON file with error handling."""
    if not os.path.exists(path):
        logger.warning(f"[WARN] File not found: {path}")
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"[ERROR] Invalid JSON in {path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"[ERROR] Failed to read {path}: {e}")
        return {}


# ================== ABI EXTRACTION ================== #
def extract_abi(possible_artifact) -> List[Dict]:
    """Handles both Hardhat artifacts and plain ABI arrays."""
    if isinstance(possible_artifact, dict) and "abi" in possible_artifact:
        abi = possible_artifact["abi"]
    elif isinstance(possible_artifact, list):
        abi = possible_artifact
    else:
        raise ValueError("Invalid ABI structure: must be a dict with 'abi' or a list.")

    if not isinstance(abi, list):
        raise ValueError("ABI must be a list of function/event definitions.")
    return abi


# ================== ABI VALIDATION ================== #
def validate_abi_structure(abi: List[Dict]) -> None:
    """Validates ABI entries and logs duplicates or malformed definitions."""
    if not abi:
        raise ValueError("ABI list is empty — deployment_info.json may be corrupted.")

    func_names = []
    for item in abi:
        if not isinstance(item, dict):
            logger.warning("[WARN] Malformed ABI entry (not a dict).")
            continue

        item_type = item.get("type")
        if item_type not in {"function", "constructor", "event", "error"}:
            logger.debug(f"[DEBUG] Skipping unsupported ABI item type: {item_type}")
            continue

        if item_type == "function":
            name = item.get("name")
            if not name:
                logger.warning(f"[WARN] Function missing name field in ABI entry: {item}")
                continue
            func_names.append(name)

    duplicates = {name for name in func_names if func_names.count(name) > 1}
    if duplicates:
        logger.warning(f"[WARN] Duplicate function names found in ABI: {', '.join(duplicates)}")


# ================== IMPLEMENTATION RESOLUTION ================== #
def get_current_implementation_abi(deployment_info: Dict) -> Tuple[str, List[Dict]]:
    """Return (version, abi) for the currently deployed implementation."""
    current_version = deployment_info.get("currentImplementation", "V1")
    implementations = deployment_info.get("implementations", {})

    for version in [current_version, "V1"]:
        if version in implementations:
            artifact_data = implementations[version].get("abi")
            try:
                abi = extract_abi(artifact_data)
                validate_abi_structure(abi)
                return version, abi
            except Exception as e:
                logger.warning(f"[WARN] Invalid ABI in {version}: {e}")
    raise FileNotFoundError("❌ No valid ABI found in deployment_info.json")


# ================== CONTRACT INSTANCE CREATION ================== #
def get_contract():
    """Return the Web3 contract instance (singleton)."""
    global _contract
    if _contract:
        return _contract

    # --- Try primary deployment_info.json --- #
    deployment_info = load_json_file(DEPLOYMENT_INFO_PATH)

    # Fallback if primary missing or invalid
    if not deployment_info or "implementations" not in deployment_info:
        logger.warning(f"[FALLBACK] Using Hardhat artifact from: {FALLBACK_ABI_PATH}")
        fallback_data = load_json_file(FALLBACK_ABI_PATH)

        if not fallback_data:
            raise FileNotFoundError("❌ No valid contract metadata found (both primary and fallback failed).")

        abi = extract_abi(fallback_data)
        validate_abi_structure(abi)
        proxy_address = fallback_data.get("address") or settings.BESU_CONTRACT_ADDRESS
        if not proxy_address:
            raise ValueError("❌ Contract address missing in Hardhat artifact or .env (BESU_CONTRACT_ADDRESS).")
        version = "Hardhat-Artifact"
    else:
        proxy_address = deployment_info.get("proxy")
        if not proxy_address:
            raise ValueError("❌ No proxy address found in deployment_info.json.")
        if not Web3.is_address(proxy_address):
            raise ValueError(f"❌ Invalid proxy address format: {proxy_address}")
        version, abi = get_current_implementation_abi(deployment_info)

    # --- Create contract instance --- #
    _contract = w3.eth.contract(
        address=Web3.to_checksum_address(proxy_address),
        abi=abi
    )

    logger.info(f"✅ Loaded contract {proxy_address} with {version} ABI ({len(abi)} functions)")
    return _contract
