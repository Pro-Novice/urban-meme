import logging
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from Services.api_response import ApiResponse
from .blockchain_services import (
    write_to_contract,
    read_from_contract,
    get_transaction_status,
    get_available_methods,
    get_contract_abi,
    get_contract_address,
    estimate_gas_for_method
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# Core Blockchain Interaction Endpoints
# ══════════════════════════════════════════════════════════════════════

@api_view(["POST"])
def blockchain_write_view(request):
    """
    Universal endpoint for writing to any smart contract method
    
    Expected payload:
    {
        "contract_name": "seedLicenseContract",
        "method_name": "applyForLicense",
        "params": [...],
        "address": "0x..." (optional),
        "private_key": "..." (optional)
    }
    """
    contract_name = request.data.get("contract_name")
    method_name = request.data.get("method_name")
    params = request.data.get("params", [])
    address = request.data.get("address")
    private_key = request.data.get("private_key")
    
    if not contract_name or not method_name:
        return ApiResponse(err="Missing required fields: contract_name, method_name", status=400)
    
    try:
        result = write_to_contract(
            contract_name=contract_name,
            method_name=method_name,
            params=params,
            address=address,
            private_key=private_key
        )
        return ApiResponse(data=result, status=200)
    except ValueError as e:
        return ApiResponse(err=str(e), status=400)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=500)


@api_view(["POST"])
def blockchain_read_view(request):
    """
    Universal endpoint for reading from any smart contract method
    
    Expected payload:
    {
        "contract_name": "seedLicenseContract",
        "method_name": "getLicenseDetails",
        "params": [123]
    }
    """
    contract_name = request.data.get("contract_name")
    method_name = request.data.get("method_name")
    params = request.data.get("params", [])
    
    if not contract_name or not method_name:
        return ApiResponse(err="Missing required fields: contract_name, method_name", status=400)
    
    try:
        result = read_from_contract(
            contract_name=contract_name,
            method_name=method_name,
            params=params
        )
        return ApiResponse(data={"result": result}, status=200)
    except ValueError as e:
        return ApiResponse(err=str(e), status=400)
    except Exception as e:
        logger.exception("Blockchain read error")
        return ApiResponse(err=f"Blockchain read failed: {str(e)}", status=500)


# ══════════════════════════════════════════════════════════════════════
# Transaction Management
# ══════════════════════════════════════════════════════════════════════

@api_view(["GET"])
def transaction_status_view(request, tx_hash):
    """Get transaction status and details by hash"""
    try:
        status = get_transaction_status(tx_hash)
        return ApiResponse(data=status, status=200)
    except Exception as e:
        logger.exception("Transaction status error")
        return ApiResponse(err=f"Failed to get transaction status: {str(e)}", status=500)


# ══════════════════════════════════════════════════════════════════════
# Contract Information & Utilities
# ══════════════════════════════════════════════════════════════════════

@api_view(["GET"])
def contract_methods_view(request, contract_name):
    """Get all available methods for a contract"""
    try:
        methods = get_available_methods(contract_name)
        return ApiResponse(data=methods, status=200)
    except Exception as e:
        logger.exception("Contract methods error")
        return ApiResponse(err=f"Failed to get contract methods: {str(e)}", status=500)


@api_view(["GET"])
def contract_abi_view(request, contract_name):
    """Get contract ABI"""
    try:
        abi = get_contract_abi(contract_name)
        return ApiResponse(data={"abi": abi}, status=200)
    except Exception as e:
        logger.exception("Contract ABI error")
        return ApiResponse(err=f"Failed to get contract ABI: {str(e)}", status=500)


@api_view(["GET"])
def contract_address_view(request, contract_name):
    """Get contract address"""
    try:
        address = get_contract_address(contract_name)
        return ApiResponse(data={"address": address}, status=200)
    except Exception as e:
        logger.exception("Contract address error")
        return ApiResponse(err=f"Failed to get contract address: {str(e)}", status=500)


@api_view(["POST"])
def estimate_gas_view(request):
    """
    Estimate gas for a method call
    
    Expected payload:
    {
        "contract_name": "seedLicenseContract",
        "method_name": "applyForLicense",
        "params": [...],
        "from_address": "0x..." (optional)
    }
    """
    contract_name = request.data.get("contract_name")
    method_name = request.data.get("method_name")
    params = request.data.get("params", [])
    from_address = request.data.get("from_address")
    
    if not contract_name or not method_name:
        return ApiResponse(err="Missing required fields: contract_name, method_name", status=400)
    
    try:
        gas_info = estimate_gas_for_method(
            contract_name=contract_name,
            method_name=method_name,
            params=params,
            from_address=from_address
        )
        return ApiResponse(data=gas_info, status=200)
    except Exception as e:
        logger.exception("Gas estimation error")
        return ApiResponse(err=f"Failed to estimate gas: {str(e)}", status=500)