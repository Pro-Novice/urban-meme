# apps/seed_licenses/services/blockchain/connection.py
import threading, requests, logging
from django.conf import settings
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

NONCE_LOCK = threading.Lock()

def get_web3():
    """Return a configured Web3 instance"""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL, session=session))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to blockchain node: {settings.BLOCKCHAIN_URL}")
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3

# Singleton Web3 instance
w3 = get_web3()

def get_default_account():
    """Load default system account"""
    if hasattr(settings, "PRIVATE_KEY") and settings.PRIVATE_KEY:
        account = w3.eth.account.from_key(settings.PRIVATE_KEY)
        return {
            "account": account,
            "address": account.address,
            "private_key": settings.PRIVATE_KEY
        }
    logger.warning("No PRIVATE_KEY found in settings")
    return None
