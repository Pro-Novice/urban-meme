import random
import logging
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

class MultiRPCWeb3:
    """Manages multiple RPC endpoints with failover and optional random selection."""

    def __init__(self, rpc_urls):
        if not rpc_urls:
            raise ValueError("No RPC URLs configured")
        self.rpc_urls = rpc_urls
        self.current_url = random.choice(rpc_urls)
        self.w3 = self._connect(self.current_url)

    def _connect(self, url):
        """Try connecting to an RPC URL."""
        logger.info(f"🔗 Connecting to blockchain node: {url}")
        w3 = Web3(Web3.HTTPProvider(url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if not w3.is_connected():
            raise ConnectionError(f"❌ Failed to connect: {url}")
        logger.info(f"✅ Connected to {url}")
        return w3

    def get_connection(self):
        """Return active Web3 connection, fallback if needed."""
        try:
            if not self.w3.is_connected():
                raise ConnectionError(f"RPC {self.current_url} disconnected")
            return self.w3
        except Exception as e:
            logger.warning(f"⚠️ RPC {self.current_url} failed: {e}")
            for url in self.rpc_urls:
                try:
                    self.w3 = self._connect(url)
                    self.current_url = url
                    return self.w3
                except Exception:
                    continue
            raise ConnectionError("❌ All RPC endpoints are unreachable")

    def get_current_url(self):
        return self.current_url
