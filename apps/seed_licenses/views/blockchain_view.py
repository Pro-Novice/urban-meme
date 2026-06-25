import logging
import time
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from utils.api_response import ApiResponse
from apps.seed_licenses.services.blockchain import (
    TransactionService,
    get_contract,
    w3,
)
from django.core.cache import cache 
from apps.seed_licenses.services.blockchain import TransactionService
from apps.seed_licenses.schemas import (
    owner_schema, contract_address_schema, contract_methods_schema,
    transaction_status_schema, blockchain_health_schema, network_info_schema,
    block_details_schema, cache_keys_schema, cache_clear_schema, redis_health_schema,
)
from utils.middleware import sensitive_view 

logger = logging.getLogger(__name__)

# Create one shared TransactionService instance
tx_service = TransactionService()
@sensitive_view
@owner_schema()
@api_view(["GET"])
def check_owner_blockchain(request):
    """
    Get the owner (admin) address from the deployed smart contract.
    Equivalent to contract.owner() call.
    """
    try:
        owner_address = tx_service.read("owner", [])
        return ApiResponse(data={"owner": owner_address}, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Failed to fetch blockchain owner address")
        return ApiResponse(err=f"Blockchain owner fetch failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)



# ===============================================================
# 1 GET Contract Address
# ===============================================================
@contract_address_schema()
@api_view(["GET"])
def contract_address_view(request):
    """
    Get deployed contract address from blockchain service.
    """
    try:
        contract = get_contract()
        return ApiResponse(
            data={"contract_address": contract.address}, status=HTTP_200_OK
        )
    except Exception as e:
        logger.exception("Failed to fetch contract address")
        return ApiResponse(
            err=f"Failed to fetch contract address: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ===============================================================
# 2️ GET All Available Methods
# ===============================================================
@contract_methods_schema()
@api_view(["GET"])
def contract_methods_view(request):
    """
    List all available read and write methods from contract ABI.
    """
    try:
        contract = get_contract()
        abi = contract.abi
        read_methods = sorted(
            [item["name"] for item in abi if item.get("stateMutability") in ["view", "pure"]]
        )
        write_methods = sorted(
            [item["name"] for item in abi if item.get("stateMutability") not in ["view", "pure"]]
        )
        return ApiResponse(
            data={"read_methods": read_methods, "write_methods": write_methods},
            status=HTTP_200_OK,
        )
    except Exception as e:
        logger.exception("Failed to fetch contract methods")
        return ApiResponse(
            err=f"Failed to get contract methods: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ===============================================================
# 3️ GET Transaction Status
# ===============================================================
@transaction_status_schema()
@api_view(["GET"])
def transaction_status_view(request, tx_hash):
    """
    Check the confirmation and metadata of a blockchain transaction.
    """
    try:
        result = tx_service.get_status(tx_hash)
        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Transaction status check failed")
        return ApiResponse(
            err=f"Failed to get transaction status: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ===============================================================
# 4️ Health Check / Node Status
# ===============================================================
@blockchain_health_schema()
@api_view(["GET"])
def blockchain_health_check(request):
    """
    Health check endpoint for blockchain connectivity.
    Verifies Web3 connection and node synchronization status.
    """
    cache_key = "blockchain_health_v2"
    cached = cache.get(cache_key)
    
    # Return cached result (30 second cache)
    if cached:
        cached["cached"] = True
        return ApiResponse(data=cached, status=HTTP_200_OK)
    
    try:
        # Quick connection check only
        connected = w3.is_connected()
        
        result = {
            "connected": connected,
            "status": "healthy" if connected else "degraded",
            "timestamp": time.time(),
            "cached": False
        }
        
        # Cache for 30 seconds
        cache.set(cache_key, result, timeout=30)
        
        return ApiResponse(data=result, status=HTTP_200_OK)
        
    except Exception as e:
        logger.exception("Blockchain health check failed")
        return ApiResponse(
            err=f"Blockchain connection failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ===============================================================
# 5️ GET Gas Price & Chain Info
# ===============================================================
@network_info_schema()
@api_view(["GET"])
def blockchain_network_info(request):
    """
    Fetch current gas price, chain ID, and basic network info.
    """
    try:
        connected = w3.is_connected()
        if not connected:
            return ApiResponse(err="Blockchain not connected", status=HTTP_400_BAD_REQUEST)

        return ApiResponse(
            data={
                "chain_id": w3.eth.chain_id,
                "gas_price": w3.eth.gas_price,
                "block_number": w3.eth.block_number,
            },
            status=HTTP_200_OK,
        )
    except Exception as e:
        logger.exception("Failed to fetch blockchain info")
        return ApiResponse(
            err=f"Error fetching blockchain info: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

# ===============================================================
# 6️ Get Block Details with Transactions
# ===============================================================
@block_details_schema()
@api_view(["GET"])
def get_block_details(request, block_number):
    """
    Get complete block info along with all transactions.
    Example: /api/blockchain/block/56526/
    """
    try:
        block_number = int(block_number)
        if block_number < 0:
            return ApiResponse(err="Block number must be positive integer", status=HTTP_400_BAD_REQUEST)
    except ValueError:
        return ApiResponse(err="Invalid block number format", status=HTTP_400_BAD_REQUEST)

    result = tx_service.get_block_with_transactions(block_number)

    if not result.get("success"):
        logger.error(f"Block fetch failed: {result['error']}")
        return ApiResponse(err=result["error"], status=HTTP_500_INTERNAL_SERVER_ERROR)

    return ApiResponse(data=result["data"], status=HTTP_200_OK)

# ===============================================================
# 7️ Cache Inspection & Management (DEBUG ONLY)
# ===============================================================
@cache_keys_schema()
@api_view(["GET"])
def view_all_cache_keys(request):
    """View all cached keys and their values (DEBUG ONLY)."""
    try:
        from django_redis import get_redis_connection  
        

        redis_client = get_redis_connection("default")
        
 
        pattern = "agri_license*"
        all_keys = redis_client.keys(pattern)
        
        cache_data = {}
        for key in all_keys:

            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            

            raw_value = redis_client.get(key)
            

            if raw_value:
                try:
                    import pickle
                    value = pickle.loads(raw_value)
                except:
                    value = raw_value.decode('utf-8') if isinstance(raw_value, bytes) else raw_value
            else:
                value = None
                
            cache_data[key_str] = value
        
        return ApiResponse(
            data={
                "total_keys": len(all_keys),
                "keys": [k.decode('utf-8') if isinstance(k, bytes) else k for k in all_keys],
                "cache_data": cache_data
            },
            status=HTTP_200_OK
        )
    except Exception as e:
        logger.exception("Failed to list cache keys")
        return ApiResponse(
            err=f"Cache inspection failed: {str(e)}", 
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================================================
# 8️ Clear Cache (DEBUG ONLY)
# ===============================================================
@cache_clear_schema()
@api_view(["GET"])
def clear_cache_view(request):
    """Clear all cache data (DEBUG ONLY)."""
    try:
        from django.core.cache import cache
        cache.clear()
        return ApiResponse(
            data={"status": "success", "message": "All cache cleared"},
            status=HTTP_200_OK
        )
    except Exception as e:
        return ApiResponse(
            err=f"Cache clear failed: {str(e)}", 
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================================================
# 9️ Redis Health Check
# ===============================================================
@redis_health_schema()
@api_view(["GET"]) 
def redis_health_check(request):
    """Check Redis cache connectivity and performance."""
    try:
        from django_redis import get_redis_connection
        
        redis_client = get_redis_connection("default")
        
        # Test Redis ping
        redis_client.ping()
        

        test_key = "agri_license:health_check_test"  # ← ADD PREFIX
        test_value = "ok"
        redis_client.set(test_key, test_value, ex=10)
        cached_value = redis_client.get(test_key)
        
        is_connected = cached_value == test_value.encode('utf-8')
        
        # Get Redis info
        info = redis_client.info()
        
        # Count keys with YOUR prefix only
        app_keys = redis_client.keys("agri_license*")  
        
        return ApiResponse(
            data={
                "redis_connected": is_connected,
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "total_keys_in_db": redis_client.dbsize(),  # ← ALL KEYS
                "app_cache_keys": len(app_keys),  
            },
            status=HTTP_200_OK if is_connected else HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.exception("Redis health check failed")
        return ApiResponse(
            err=f"Redis connection failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )
