import asyncio
import random
import time
import logging
from typing import Any, Dict, List, Tuple, Optional

from web3 import Web3, AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware
from web3 import AsyncHTTPProvider


logger = logging.getLogger(__name__)


# ==========================================
# Node Health & Performance Tracker
# ==========================================
class _NodeState:
    """Tracks health and latency for each RPC endpoint."""

    def __init__(self, url: str):
        self.url = url
        self.latency_ms: float = 200.0
        self.consecutive_failures: int = 0
        self.last_failure_ts: float = 0.0
        self.success_count: int = 0
        self.error_count: int = 0

    def record_success(self, latency_ms: float):
        alpha = 0.3
        self.latency_ms = alpha * latency_ms + (1 - alpha) * self.latency_ms
        self.consecutive_failures = 0
        self.success_count += 1

    def record_failure(self):
        self.error_count += 1
        self.consecutive_failures += 1
        self.last_failure_ts = time.time()

    def score(self) -> float:
        """Lower = better node. Combines latency and error penalty."""
        penalty = self.consecutive_failures * 800.0
        return self.latency_ms + penalty

    def is_healthy(self, backoff_seconds: int = 20) -> bool:
        """Avoid recently failing nodes temporarily."""
        if self.consecutive_failures == 0:
            return True
        return (time.time() - self.last_failure_ts) > backoff_seconds


# ==========================================
# Unified MultiRPCWeb3
# ==========================================
class MultiRPCWeb3:
    """
    Intelligent Web3 manager with:
    ✅ Async parallelism (via asyncio)
    ✅ Adaptive load-balancing
    ✅ Failover and latency tracking
    ✅ Compatible with both sync and async contexts
    """

    def __init__(self, rpc_urls: List[str], max_concurrency_per_node: int = 15):
        if not rpc_urls:
            raise ValueError("No RPC URLs configured")

        self.rpc_urls = list(dict.fromkeys(rpc_urls))
        self._nodes: Dict[str, _NodeState] = {u: _NodeState(u) for u in self.rpc_urls}
        self._w3_cache: Dict[str, AsyncWeb3] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {
            u: asyncio.Semaphore(max_concurrency_per_node) for u in self.rpc_urls
        }
        self._lock = asyncio.Lock()
        self._current_url: Optional[str] = None

    # ------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------
    async def _connect(self, url: str) -> AsyncWeb3:
        logger.info(f"🔗 Connecting to blockchain node: {url}")
        w3 = AsyncWeb3(AsyncHTTPProvider(url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if not await w3.is_connected():
            raise ConnectionError(f"❌ Failed to connect: {url}")
        logger.info(f"✅ Connected to {url}")
        return w3

    async def _get_or_create_w3(self, url: str) -> AsyncWeb3:
        async with self._lock:
            if url not in self._w3_cache:
                self._w3_cache[url] = await self._connect(url)
            return self._w3_cache[url]

    # ------------------------------------------------------
    # Node Selection
    # ------------------------------------------------------
    async def _choose_best_node(self) -> Tuple[str, _NodeState]:
        healthy = [n for n in self._nodes.values() if n.is_healthy()]
        if not healthy:
            healthy = list(self._nodes.values())

        if len(healthy) == 1:
            return healthy[0].url, healthy[0]

        a, b = random.sample(healthy, 2)
        best = a if a.score() <= b.score() else b
        return best.url, best

    async def _get_web3(self) -> Tuple[str, AsyncWeb3]:
        """Return best available AsyncWeb3 connection."""
        try:
            if self._current_url:
                w3 = await self._get_or_create_w3(self._current_url)
                if await w3.is_connected():
                    return self._current_url, w3
        except Exception:
            pass

        for _ in range(len(self._nodes)):
            url, node = await self._choose_best_node()
            try:
                w3 = await self._get_or_create_w3(url)
                if await w3.is_connected():
                    async with self._lock:
                        self._current_url = url
                    return url, w3
            except Exception as e:
                node.record_failure()
                logger.warning(f"⚠️ RPC {url} failed during selection: {e}")

        raise ConnectionError("❌ All RPC endpoints are unreachable")

    # ------------------------------------------------------
    # Core Async RPC Call
    # ------------------------------------------------------
    async def call(self, method: str, params: List[Any]) -> Any:
        """Make a single async JSON-RPC call with failover + latency tracking."""
        url, w3 = await self._get_web3()
        sem = self._semaphores[url]
        start = time.monotonic()

        async with sem:
            try:
                result = await w3.provider.make_request(method, params)
                latency = (time.monotonic() - start) * 1000
                self._nodes[url].record_success(latency)
                return result
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                self._nodes[url].record_failure()
                logger.warning(f"❌ RPC {method} failed on {url}: {e}")
                raise

    # ------------------------------------------------------
    # Bulk Calls in Parallel
    # ------------------------------------------------------
    async def run_parallel(self, calls: List[Tuple[str, List[Any]]]) -> List[Any]:
        """
        Run many JSON-RPC calls in parallel:
        Example:
            calls = [("eth_getBlockByNumber", [hex(n), True]) for n in range(68000, 68100)]
            results = await rpc_manager.run_parallel(calls)
        """
        async def _execute(method: str, params: List[Any]):
            try:
                return await self.call(method, params)
            except Exception as e:
                return {"error": str(e)}

        tasks = [asyncio.create_task(_execute(m, p)) for m, p in calls]
        return await asyncio.gather(*tasks)

    # ------------------------------------------------------
    # Sync Compatibility Layer
    # ------------------------------------------------------
    def get_connection(self) -> Web3:
        """
        For legacy sync code paths (e.g. Django views / TransactionService).
        Automatically wraps async connection into a blocking call.
        """
        try:
            return asyncio.run(self._get_sync_wrapper())
        except RuntimeError:
            # already inside an event loop (e.g., in Celery async)
            return asyncio.get_event_loop().run_until_complete(self._get_sync_wrapper())

    async def _get_sync_wrapper(self) -> Web3:
        url, async_w3 = await self._get_web3()
        # Create a lightweight sync proxy wrapper
        return Web3(Web3.HTTPProvider(url))

    def get_current_url(self) -> Optional[str]:
        return self._current_url

    def get_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Return current node stats for debugging/monitoring."""
        return {
            url: {
                "latency_ms": n.latency_ms,
                "failures": n.consecutive_failures,
                "healthy": n.is_healthy(),
                "score": n.score(),
            }
            for url, n in self._nodes.items()
        }
