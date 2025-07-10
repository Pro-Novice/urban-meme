import hashlib
import logging
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK

from Services.api_response import ApiResponse
from .blockchain_services import (
    format_api_response,
    write_to_contract,
    read_from_contract,
    get_transaction_status,
    get_available_methods,
    get_contract_abi,
    get_contract_address,
    estimate_gas_for_method,
    get_all_contract_addresses
    
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


@api_view(["GET"])
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
        return ApiResponse(format_api_response(True, result), status=200)
    except ValueError as e:
        return ApiResponse(format_api_response(False, error=str(e)), status=500)
    except Exception as e:
        logger.exception("Blockchain read error")
        return ApiResponse(format_api_response(False, error=f"Blockchain read failed: {str(e)}"), status=500)


# get_license_basic_info
@api_view(["GET"])
def get_license_basic_info(request, license_id):
    license_id = int(license_id) if license_id.isdigit() else None
    if not license_id:
        return ApiResponse(format_api_response(False, error="Missing license_id in URL"), status=400)
    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getLicenseBasicInfo",
            params=[license_id]
        )
        return ApiResponse(format_api_response(True, data=result))
    except Exception as e:
        logger.exception("Fetch license basic info failed")
        return ApiResponse(format_api_response(False, error=f"License basic info fetch failed: {str(e)}"), status=500 )

# Verify Document Hash
@api_view(["POST"])
@parser_classes([MultiPartParser])
def generate_document_hash(request):
    file = request.FILES.get("file")
    if not file:
        return ApiResponse(err="File is required", status=400)

    try:
        hash_func = hashlib.sha256()
        for chunk in file.chunks():
            hash_func.update(chunk)
        file_hash = hash_func.hexdigest()
        return ApiResponse(data={"hash": file_hash})
    except Exception as e:
        logger.exception("Hash generation failed")
        return ApiResponse(err=f"Document hash generation failed: {str(e)}", status=500)

# verify_document
@api_view(["POST"])
def verify_document(request):
    required_fields = ["license_id", "document_type", "document_hash", "is_verified", "remarks"]
    for field in required_fields:
        if field not in request.data or request.data[field] in [None, ""]:
            return ApiResponse(err=f"Missing or empty field: {field}", status=400)

    try:
        license_id = int(request.data["license_id"])
        document_type = int(request.data["document_type"])
        is_verified = request.data["is_verified"] in [True, "true", "True", 1, "1"]
        document_hash = str(request.data["document_hash"])
        remarks = str(request.data["remarks"])
    except (ValueError, TypeError) as e:
        return ApiResponse(err=f"Invalid input types: {str(e)}", status=400)

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="verifyDocument",
            params=[license_id, document_type, document_hash, is_verified, remarks],
            address=request.data.get("address"),
            private_key=request.data.get("private_key")
        )
        return ApiResponse(data=result)
    except Exception as e:
        logger.exception("Document verification failed")
        return ApiResponse(err=f"Document verification failed: {str(e)}", status=500)


# Get All Document Statuses with type and license_id
@api_view(["GET"])
def get_document_status(request, license_id, document_type):
    license_id = int(license_id) if license_id.isdigit() else None
    document_type = int(document_type) if document_type.isdigit() else None
    if not license_id or not document_type:
        return ApiResponse(format_api_response(False, error="Invalid license_id or document_type"), status=400)

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getDocumentStatus",
            params=[license_id, document_type]
        )
        return ApiResponse(format_api_response(True, data={
            "isVerified": result[0],
            "verifiedBy": result[1],
            "verificationDate": result[2],
            "remarks": result[3],
            "documentHash": result[4]
        }))
    except Exception as e:
        logger.exception("Fetch document status failed")
        return ApiResponse(format_api_response(False, error=f"Document status fetch failed: {str(e)}"), status=500)


# Get All Document Statuses for a License_id
@api_view(["GET"])
def get_all_document_statuses(request, license_id):
    license_id = int(license_id) if license_id.isdigit() else None
    if not license_id:
        return ApiResponse(format_api_response(False, error="Missing license_id in URL"), status=400)

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getAllDocumentStatuses",
            params=[license_id]
        )
        return ApiResponse(format_api_response(True, data={
            "documentTypes": result[0],
            "verificationStatuses": result[1],
            "remarks": result[2]
        }))
    except Exception as e:
        logger.exception("Fetch all document statuses failed")
        return ApiResponse(format_api_response(False, error=f"All document statuses fetch failed: {str(e)}"), status=500)

# add_inspection_feedback
@api_view(["POST"])
def add_inspection_feedback(request):
    required_fields = ["license_id", "inspector", "feedback_type", "remarks"]
    for field in required_fields:
        if field not in request.data or request.data[field] in [None, ""]:
            return ApiResponse(err=f"Missing or empty field: {field}", status=400)

    try:
        license_id = int(request.data["license_id"])
        inspector = str(request.data["inspector"])
        feedback_type = int(request.data["feedback_type"])
        remarks = str(request.data["remarks"])
    except (ValueError, TypeError) as e:
        return ApiResponse(err=f"Invalid input types: {str(e)}", status=400)

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="addInspectionFeedback",
            params=[license_id, inspector, feedback_type, remarks],
            address=request.data.get("address"),
            private_key=request.data.get("private_key")
        )
        return ApiResponse(data=result)
    except Exception as e:
        logger.exception("Add inspection feedback failed")
        return ApiResponse(err=f"Inspection feedback submission failed: {str(e)}", status=500)

# Get All Inspection Feedback
@api_view(["GET"])
def get_all_inspection_feedback(request, license_id):
    license_id = int(license_id) if license_id.isdigit() else None
    if not license_id:
        return ApiResponse(format_api_response(False, error="Missing license_id in URL"), status=400)
    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getAllInspectionFeedback",
            params=[license_id]
        )
        return ApiResponse(format_api_response(True, data=result))
    except Exception as e:
        logger.exception("Fetch inspection feedback failed")
        return ApiResponse(format_api_response(False, error=f"Inspection feedback fetch failed: {str(e)}"), status=500)

# Count Feedback by Type
@api_view(["GET"])
def count_feedback_by_type(request, license_id, feedback_type):
    try:
        license_id = int(license_id)
        feedback_type = int(feedback_type)
    except (ValueError, TypeError):
        return ApiResponse(format_api_response(False, error="Invalid license_id or feedback_type (must be integers)"), status=400)

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="countFeedbackByType",
            params=[license_id, feedback_type]
        )
        return ApiResponse(format_api_response(True, data={"count": result}))
    except Exception as e:
        logger.exception("Count feedback by type failed")
        return ApiResponse(format_api_response(False, error=f"Count feedback fetch failed: {str(e)}"), status=500)
    
# list_all_functions (utility)
@api_view(["GET"])
def list_all_contract_functions(request):
    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="listAllFunctions",
            params=[]
        )
        return ApiResponse(format_api_response(True, data={"functions": result}))
    except Exception as e:
        logger.exception("List contract functions failed")
        return ApiResponse(format_api_response(False, error=f"Contract functions listing failed: {str(e)}"), status=500)

# get_license_counter
@api_view(["GET"])
def get_license_counter(request):
    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="licenseIdCounter",
            params=[]
        )
        return ApiResponse(format_api_response(True, data=result))
    except Exception as e:
        logger.exception("Get license counter failed")
        return ApiResponse(format_api_response(False, error=f"License counter fetch failed: {str(e)}"), status=500)

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
    """Get contract address(es) - supports 'all' to return all addresses"""
    try:
        # Special case: return all contract addresses
        if contract_name.lower() == 'all':
            all_addresses = get_all_contract_addresses()
            return ApiResponse(data=all_addresses, status=200)
        
        # Return specific contract address
        address = get_all_contract_addresses(contract_name)
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