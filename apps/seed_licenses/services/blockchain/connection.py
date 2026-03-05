# apps/seed_licenses/services/blockchain/connection.py
import threading, requests, logging
from django.conf import settings
from web3.middleware import ExtraDataToPOAMiddleware   
from apps.seed_licenses.services.web3_provider import MultiRPCWeb3
from apps.seed_licenses.services.multi_account_manager import multi_account_manager
logger = logging.getLogger(__name__)

# Thread-safe nonce management
NONCE_LOCK = threading.Lock()


def get_web3():
    """
    Return a configured Web3 instance using MultiRPCWeb3 for
    automatic failover, connection pooling, and PoA compatibility.
    """
    try:
        # Setup optimized HTTP session
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Initialize Multi-RPC (with random load balancing + failover)
        multi_rpc = MultiRPCWeb3(settings.RPC_URLS)
        w3 = multi_rpc.get_connection()

        #  Inject PoA middleware safely (without isinstance check)
        middleware_names = [mw.__class__.__name__ for mw in w3.middleware_onion]
        if "ExtraDataToPOAMiddleware" not in middleware_names:
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            logger.info("✅ ExtraDataToPOAMiddleware injected (Besu QBFT compatibility)")

        logger.info(f"✅ Connected to blockchain RPC: {multi_rpc.get_current_url()}")
        return w3, multi_rpc

    except Exception as e:
        logger.error(f"❌ Failed to initialize Web3 connection: {e}")
        raise


# Global singleton
w3, multi_rpc = get_web3()


def get_default_account():
    """Load default system wallet from PRIVATE_KEY."""
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


def get_random_account():
    """Get a random account from multi-account manager."""
    account = multi_account_manager.get_random_account()
    if account:
        return {
            "account": w3.eth.account.from_key(account["private_key"]),
            "address": account["address"],
            "private_key": account["private_key"],
            "source": account["source"]
        }
    return None


def get_current_rpc_url():
    """Return active RPC URL (for logging or debugging)."""
    try:
        return multi_rpc.get_current_url()
    except Exception:
        return "Unknown"


def get_accounts_info():
    """Get information about all available accounts."""
    return multi_account_manager.get_accounts_info()


rpc_manager = multi_rpc