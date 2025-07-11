import hashlib
import logging
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

from Services.api_response import ApiResponse
from .blockchain_services import (
    write_to_contract,
    read_from_contract,
    get_transaction_status,
    get_available_methods,
    get_contract_abi,
    get_contract_address,
    estimate_gas_for_method,
    get_all_contract_addresses

)
from .serialzers import AddOfficerSerializer, CreateLicenseSerializer, UpdateLicenseStatusSerializer, \
    VerifyDocumentSerializer, AddInspectionFeedbackSerializer, REVERSE_OFFICER_ROLE_MAP

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Backend Interaction Endpoints
# ══════════════════════════════════════════════════════════════════

# 1. Initialize Blockchain contract apis

# 1. Initialize Blockchain contract apis
@api_view(["GET"])
def initialize_blockchain_contract(request):
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

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="initialize",
            params=[],
            # address=address,
            # private_key=private_key
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

#2. Check owner of the blockchain
@api_view(["GET"])
def check_owner_blockchain(request):
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

    try:

        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="owner",
            params=[],
            # address=address,
            # private_key=private_key
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


#3. check admin of the blockchain
@api_view(["GET"])
def check_admin_blockchain(request):
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

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="admin",
            params=[],
            # address=address,
            # private_key=private_key
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

#4. check total License count
@api_view(["GET"])
def check_total_license_count(request):
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

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="licenseIdCounter",
            params=[],
            # address=address,
            # private_key=private_key
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

#5. Add Officer according to level
@api_view(["POST"])
def add_officer_view(request):
    # print("DEBUG: request.data =", request.data)
    serializer = AddOfficerSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=400)

    validated = serializer.validated_data

    # Prepare parameters for smart contract
    level = validated["officer_level"]

    params = [
        validated["officer_address"],
        validated["officer_name"],
        validated["officer_id"],
        validated["officer_role"],  # already converted to enum
        validated["department"],
        level,  # already converted to enum
        validated.get("state", ""),
        validated.get("district", ""),
        validated.get("division", "")  ]
    print("params %s", params)

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="addOfficer",
            params=params,

        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
def get_officer_role(request, address):
    """
    Get officer role by their blockchain address.
    """
    if not address:
        return ApiResponse(err="Missing officer address in URL", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getOfficerRole",
            params=[address],
        )
        role_id = result.get("role")
        role_name = REVERSE_OFFICER_ROLE_MAP.get(role_id, "UNKNOWN_ROLE")
        return ApiResponse(data={"role_id": role_id, "role_name": role_name}, status=HTTP_200_OK)

    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain read error")
        return ApiResponse(err=f"Blockchain read failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def get_officer_details(request, address):
    """
    Get officer details by blockchain address.
    """
    if not address:
        return ApiResponse(err="Missing officer address in URL", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getOfficerDetails",
            params=[address],
        )
        return ApiResponse(data=result, status=HTTP_200_OK)

    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain read error")
        return ApiResponse(err=f"Blockchain read failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
# 8. create License for all the levels

@api_view(["POST"])
def create_license_view(request):
    """
    Universal endpoint to create a license on smart contract.

    Expected JSON payload:
    {
        "license_category": "SEED",
        "admin_level": "STATE",
        "applicant_name": "John Doe",
        "aadhaar_number": "123412341234",
        "business_name": "John's Farm",
        "state": "RAJASTHAN",       # optional, depending on level
        "district": "",            # optional, depending on level
        "division": ""             # optional, depending on level
        # "address": "0x...",      # optional, for contract call
        # "private_key": "..."     # optional, for contract call
    }
    """
    serializer = CreateLicenseSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    params = [
        validated["license_category"],
        validated["admin_level"],
        validated["applicant_name"],
        validated["aadhaar_number"],
        validated["business_name"],
        validated.get("state", ""),
        validated.get("district", ""),
        validated.get("division", "")
    ]

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="createLicense",
            params=params,
            # address=request.data.get("address"),
            # private_key=request.data.get("private_key")
        )
        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception("Create license failed")
        return ApiResponse(err=f"Create license failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
def update_license_status_view(request):
    """
    Update the status of a license on the blockchain.

    Expected JSON payload:
    {
        "license_id": 123,
        "status": "APPROVED",   # will be converted to enum int by serializer
        "remarks": "Status updated by admin"
        # "address": "0x...",   # optional
        # "private_key": "..."  # optional
    }
    """
    serializer = UpdateLicenseStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    params = [
        validated["license_id"],
        validated["status"],  # enum integer
        validated["remarks"]
    ]

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="updateStatus",
            params=params,
            # address=request.data.get("address"),
            # private_key=request.data.get("private_key")
        )
        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception("Update license status failed")
        return ApiResponse(err=f"Update license status failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

# 10. Update License Action History
@api_view(["GET"])
def get_license_action_history(request,license_id):
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
    license_id = int(license_id)
    if not license_id:
        return ApiResponse(err="Missing license_id in URL", status=HTTP_400_BAD_REQUEST)
    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getLicenseActionHistory",
            params=[
                license_id,
            ],
            # address=address,
            # private_key=private_key
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
#11. get_license_basic_info
@api_view(["GET"])
def get_license_basic_info(request, license_id):
    license_id = int(license_id)
    if not license_id:
        return ApiResponse( err="Missing license_id in URL", status=HTTP_400_BAD_REQUEST)
    #
    # if not license_id.isdigit():
    #     return ApiResponse( err="License id should be an integer", status=HTTP_400_BAD_REQUEST)
    try:
        result = read_from_contract(
                contract_name="LicenseSystemV1",
                method_name="getLicenseBasicInfo",
                params=[license_id]
        )
        return ApiResponse(data=result,status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Fetch license basic info failed")
        return ApiResponse(err=f"License basic info fetch failed: {str(e)}",
                               status=HTTP_500_INTERNAL_SERVER_ERROR)
# 12.Verify Document Hash
@api_view(["POST"])
@parser_classes([MultiPartParser])
def generate_document_hash(request):
    file = request.FILES.get("file")
    if not file:
        return ApiResponse(err="File is required", status=HTTP_400_BAD_REQUEST)

    try:
        hash_func = hashlib.sha256()
        for chunk in file.chunks():
            hash_func.update(chunk)
        file_hash = hash_func.hexdigest()
        return ApiResponse(data={"hash": file_hash},status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Hash generation failed")
        return ApiResponse(err=f"Document hash generation failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

#13. verify_document
@api_view(["POST"])
def verify_document(request):
    serializer = VerifyDocumentSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="verifyDocument",
            params=[
                validated_data["license_id"],
                validated_data["document_type"],
                validated_data["document_hash"],
                validated_data["is_verified"],
                validated_data["remarks"]
            ],
            # address=validated_data.get("address"),
            # private_key=validated_data.get("private_key")
        )
        if (
                isinstance(result, dict) and
                result.get("success") is False and
                "Gas estimation failed" in result.get("error", "") and
                "License not found" in result.get("details", "")
        ):
            return ApiResponse(err="License not found. Please check the license ID.", status=HTTP_400_BAD_REQUEST)
        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Document verification failed")
        return ApiResponse(err=f"Document verification failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
#13. Get All Document Statuses with type and license_id
@api_view(["GET"])
def get_document_status(request, license_id, document_type):
    # license_id = int(license_id) if license_id.isdigit() else None
    # document_type = int(document_type)
    # if not license_id or not document_type:
    #     return ApiResponse(err=f"Invalid license_id or document_type: ", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
                contract_name="LicenseSystemV1",
                method_name="getDocumentStatus",
                params=[license_id, document_type]
            )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Fetch document status failed")
        return ApiResponse(err=f"Document status fetch failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

#14. Get All Document Statuses for a License_id
@api_view(["GET"])
def get_all_document_status(request, license_id):
    license_id = int(license_id) if license_id.isdigit() else None
    if not license_id:
        return ApiResponse(err="Missing license_id in URL", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
                contract_name="LicenseSystemV1",
                method_name="getAllDocumentStatuses",
                params=[license_id]
            )

        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Fetch all document statuses failed")
        return ApiResponse(err=f"All document statuses fetch failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

#15. add_inspection_feedback
@api_view(["POST"])
def add_inspection_feedback(request):
    serializer = AddInspectionFeedbackSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="addInspectionFeedback",
            params=[
                data["license_id"],
                data["inspector"],
                data["feedback_type"],
                data["remarks"]
            ],
            # address=data.get("address"),
            # private_key=data.get("private_key")
        )
        if (
                isinstance(result, dict) and
                result.get("success") is False and
                "Gas estimation failed" in result.get("error", "") and
                "License not found" in result.get("details", "")
        ):
            return ApiResponse(err=f"License not found. Please check the license ID: ", status=HTTP_400_BAD_REQUEST)
        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Add inspection feedback failed")
        return ApiResponse(
            err=f"Inspection feedback submission failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
#16. Get All Inspection Feedback
@api_view(["GET"])
def get_all_inspection_feedback(request, license_id):

    license_id = int(license_id)
    if license_id is None:
        return ApiResponse(err=f"Missing license_id in URL:", status=HTTP_400_BAD_REQUEST)
    # if not license_id.isdigit():
    #     return ApiResponse(err="License id should be in digit", status=HTTP_400_BAD_REQUEST)
    try:
        result = read_from_contract(
                contract_name="LicenseSystemV1",
                method_name="getAllInspectionFeedback",
                params=[license_id]
            )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Fetch inspection feedback failed")
        return ApiResponse(err=f"Inspection feedback fetch failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

#17. Count Feedback by Type
@api_view(["GET"])
def count_feedback_by_type(request, license_id, feedback_type):
    try:
        license_id = int(license_id)
        feedback_type = int(feedback_type)
    except (ValueError, TypeError):
        return ApiResponse(err=f"Invalid license_id or feedback_type (must be integers):", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
                contract_name="LicenseSystemV1",
                method_name="countFeedbackByType",
                params=[license_id, feedback_type]
            )
        return ApiResponse(data={"count": result}, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Count feedback by type failed")
        return ApiResponse(err=f"Count feedback fetch failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

# ══════════════════════════════════════════════════════════════════
# Core Blockchain Interaction Endpoints
# ══════════════════════════════════════════════════════════════════

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
        return ApiResponse(data=result, status=200)
    except ValueError as e:
        return ApiResponse(err=str(e), status=500)
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