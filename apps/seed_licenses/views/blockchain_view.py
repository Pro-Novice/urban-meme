import logging
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

from apps.seed_licenses.services.blockchain import TransactionService

logger = logging.getLogger(__name__)

# Create one shared TransactionService instance
tx_service = TransactionService()

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
@api_view(["GET"])
def blockchain_health_check(request):
    """
    Health check endpoint for blockchain connectivity.
    Verifies Web3 connection and node synchronization status.
    """
    try:
        connected = w3.is_connected()
        latest_block = w3.eth.block_number if connected else None
        node_info = w3.client_version if connected else "Not connected"
        return ApiResponse(
            data={
                "connected": connected,
                "latest_block": latest_block,
                "node_info": node_info,
            },
            status=HTTP_200_OK,
        )
    except Exception as e:
        logger.exception("Blockchain health check failed")
        return ApiResponse(
            err=f"Blockchain connection failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ===============================================================
# 5️ GET Gas Price & Chain Info
# ===============================================================
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
