# apps/seed_licenses/services/blockchain/connection.py
import threading, requests, logging
from django.conf import settings
from apps.seed_licenses.services.web3_provider import MultiRPCWeb3


logger = logging.getLogger(__name__)

# Thread safety for transaction nonces
NONCE_LOCK = threading.Lock()


def get_web3():
    """
    Return a configured Web3 instance using MultiRPCWeb3 for
    automatic failover and connection pooling.
    """
    try:
        # Setup requests session for performance
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Initialize Multi-RPC manager with all URLs from settings
        multi_rpc = MultiRPCWeb3(settings.RPC_URLS)

        # Get a working connection (it will test connectivity)
        w3 = multi_rpc.get_connection()

        logger.info(f"✅ Connected to blockchain RPC: {multi_rpc.get_current_url()}")
        return w3, multi_rpc

    except Exception as e:
        logger.error(f"❌ Failed to initialize Web3 connection: {e}")
        raise


# Initialize once and reuse globally
w3, multi_rpc = get_web3()


def get_default_account():
    """
    Load default system account (admin wallet) for on-chain writes.
    """
    if hasattr(settings, "PRIVATE_KEY") and settings.PRIVATE_KEY:
        try:
            account = w3.eth.account.from_key(settings.PRIVATE_KEY)
            return {
                "account": account,
                "address": account.address,
                "private_key": settings.PRIVATE_KEY,
            }
        except Exception as e:
            logger.error(f"Error loading default account: {e}")
            return None

    logger.warning("No PRIVATE_KEY found in settings — blockchain writes may fail.")
    return None


def get_current_rpc_url():
    """
    Utility to expose current active RPC URL (for diagnostics/logging).
    """
    try:
        return multi_rpc.get_current_url()
    except Exception:
        return "Unknown"
