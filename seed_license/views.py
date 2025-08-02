import hashlib
import logging
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR, HTTP_404_NOT_FOUND

from Services.api_response import ApiResponse
from .blockchain_services import (
    write_to_contract,
    read_from_contract,
    get_transaction_status,
    get_available_methods,
    get_contract_abi,
    get_contract_address,
    estimate_gas_for_method,
    get_all_contract_addresses, FEEDBACK_TYPES

)
from .enums import LicenseStatusEnum, DoctypeEnum, LICENSE_STATUS_REVERSE, REVERSE_OFFICER_ROLE

from .serialzers import SubmitLicenseApplicationSerializer, UpdateLicenseStatusSerializer, VerifyDocumentSerializer, AddInspectionFeedbackSerializer

logger = logging.getLogger(__name__)

# Valid transitions for status progression
VALID_STATUS_TRANSITIONS = {
    LicenseStatusEnum.SUBMITTED.value: [LicenseStatusEnum.UNDER_REVIEW.value],
    LicenseStatusEnum.UNDER_REVIEW.value: [LicenseStatusEnum.DOCUMENTS_VERIFIED.value, LicenseStatusEnum.REJECTED.value],
    LicenseStatusEnum.DOCUMENTS_VERIFIED.value: [LicenseStatusEnum.INSPECTION_SCHEDULED.value],
    LicenseStatusEnum.INSPECTION_SCHEDULED.value: [LicenseStatusEnum.INSPECTION_COMPLETED.value],
    LicenseStatusEnum.INSPECTION_COMPLETED.value: [LicenseStatusEnum.APPROVED.value, LicenseStatusEnum.REJECTED.value],
    LicenseStatusEnum.APPROVED.value: [LicenseStatusEnum.REVOKED.value, LicenseStatusEnum.EXPIRED.value],
    LicenseStatusEnum.EXPIRED.value: [LicenseStatusEnum.RENEWED.value], 
}

# 1. Initialize Blockchain contract
@api_view(["GET"])
def initialize_blockchain_contract(request):
    # Endpoint for intializing the blockchain contract
    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="initialize",
            params=[]
        )
        if not result.get("status", "") == "confirmed":
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

# 2. Check owner of the blockchain
@api_view(["GET"])
def check_owner_blockchain(request):
    # Endpoint to check the owner of the blockchain contract
    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="owner",
            params=[]
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# 3. check total License count
@api_view(["GET"])
def check_total_license_count(request):
    """ Endpoint to get the total number of licenses created in the blockchain.
    This is useful for tracking the number of licenses issued.
    """
    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="licenseIdCounter",
            params=[]
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# 4. Submit License Application for all the levels
@api_view(["POST"])
def submit_license_application(request):
    """
    Create a new license by interacting with the smart contract.
    Expected payload:
    {
        "license_category": "AGRICULTURE",
        "admin_level": "DISTRICT",
        "applicant_name": "John Doe",
        "aadhaar_number": "123456789012",
        "business_name": "John's Farm",
        "business_address": "123 Farm Lane, Jaipur",
        "state": "RAJASTHAN",  # Hardcoded in contract
        "district": "Jaipur",
        "division": "North"
    }
    """
    serializer = SubmitLicenseApplicationSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    params = [
        validated["license_category"],
        validated["license_level"],
        validated["applicant_name"],
        validated["aadhaar_number"],
        validated["business_name"],
        validated["business_address"],
        validated["district"],
        validated["division"]
    ]

    try:
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="submitLicenseApplication",
            params=params
        )
       
        if not result.get("status", "") == "confirmed":
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception("Create license failed")
        return ApiResponse(err=f"Create license failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# 5. get_license_basic_info
@api_view(["GET"])
def get_license_basic_info(request, license_id):
    """ Fetch basic license information by ID. """
    try:
        license_id = int(license_id)
        if license_id <= 0:
            return ApiResponse(err="License ID must be positive integer", status=HTTP_400_BAD_REQUEST)
            
    except ValueError:
        return ApiResponse(err="License ID must be a valid integer", status=HTTP_400_BAD_REQUEST)

    try:
        # 1. First check if license exists
        exists = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="licenseIdExists",
            params=[license_id]
        )
        
        if not exists:
            return ApiResponse(err=f"License ID {license_id} not found", status=HTTP_404_NOT_FOUND)

        # 2. Only fetch details if license exists
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getLicenseBasicInfo",
            params=[license_id]
        )

        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception(f"License fetch failed for ID {license_id}")
        return ApiResponse(
            err=f"License information unavailable: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )


# 6. Get License Action History
@api_view(["GET"])
def get_license_action_history(request, license_id):
    """ Fetch license action history by ID. """
    try:
        license_id = int(license_id)
        if license_id <= 0:
            return ApiResponse(err="License ID must be positive integer", status=HTTP_400_BAD_REQUEST)
    except ValueError:
        return ApiResponse(err="License ID must be a valid integer", status=HTTP_400_BAD_REQUEST)
   
    try:
        # 1. First check if license exists
        exists = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="licenseIdExists",
            params=[license_id]
        )
        
        if not exists:
            return ApiResponse(err=f"License ID {license_id} not found", status=HTTP_404_NOT_FOUND)
        
        # 2. Fetch action history
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getLicenseActionHistory",
            params=[
                license_id,
            ]
        )

        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)



# 7. Update License Status
@api_view(["POST"])
def update_license_status_view(request):
    """ Update the status of an existing license.
    Expected payload:
    {
        "license_id": 123,
        "status": "APPROVED",
        "remarks": "License approved after review",
        "officer_name": "John Doe",
        "role": "JOINT_DIRECTOR",
        "renewal_period_days": 365  # only needed if status is APPROVED
    }
    """

    serializer = UpdateLicenseStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    print("Validated data:", validated)  # Debugging line to check validated data
    license_id = validated["license_id"]
    new_status = validated["status"]            
    remarks = validated["remarks"]
    officer_name = validated["officer_name"]
    role = validated["role"]                    
    renewal_period_days = validated.get("renewal_period_days", 0)

    try:
        # 1. Fetch current license info
        current_data = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getLicenseBasicInfo",
            params=[license_id]
        )
        current_status_str = current_data["status"]
        current_status = LicenseStatusEnum.from_string(current_status_str)

        # 2. Validate allowed status transition
        allowed_next = VALID_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next:
            return ApiResponse(
                err=f"Invalid status transition from {LICENSE_STATUS_REVERSE[current_status]} to {LICENSE_STATUS_REVERSE[new_status]}",
                status=HTTP_400_BAD_REQUEST
            )

        # 3. Call contract method
        result = write_to_contract(
            contract_name="LicenseSystemV1",
            method_name="updateLicenseStatus",
            params=[
                license_id,
                new_status,
                officer_name,
                role,
                remarks,
                renewal_period_days  
            ],
        )

        if not result.get("status", "") == "confirmed":
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)

        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception("Update license status failed")
        return ApiResponse(err=f"Update license status failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

# 12.Verify Document Hash
@api_view(["POST"])
@parser_classes([MultiPartParser])
def generate_document_hash(request):
    """ Generate a SHA-256 hash for a document file.
    Expected payload:
    {
        "file": <file>
    }
    """
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
    """ Verify a document's hash and update its status in the blockchain.
    Expected payload:
    {
        "license_id": 123,
        "document_type": 0,
    }
    """
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
        if not result.get("success"):
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Document verification failed")
        return ApiResponse(err=f"Document verification failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
#13. Get All Document Statuses with type and license_id
@api_view(["GET"])
def get_document_status(request, license_id, document_type):
    """ Fetch the status of a specific document for a given license.
    """
    try:
        license_id = int(license_id)
        document_type = int(document_type)

        # Validate that the int value is in DoctypeEnum
        try:
            doc_enum = DoctypeEnum(document_type)
        except ValueError:
            return ApiResponse(
                err=f"Invalid document_type: {document_type}. Must be between 0 and {len(DoctypeEnum) - 1}.",
                status=HTTP_400_BAD_REQUEST
            )

        # Call contract
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getDocumentStatus",
            params=[license_id, document_type]
        )

        if not result.get("isVerified", False):
            return ApiResponse(
                err=f"{doc_enum.name} not verified yet.",
                status=HTTP_404_NOT_FOUND
            )

        return ApiResponse(data=result, status=HTTP_200_OK)

    except ValueError:
        return ApiResponse(
            err="Invalid license_id or document_type. Must be integers.",
            status=HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.exception("Fetch document status failed")
        return ApiResponse(
            err=f"Document status fetch failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )

#14. Get All Document Statuses for a License_id
@api_view(["GET"])
def get_all_document_status(request, license_id):
    """ Fetch the status of all documents for a given license.
    """
    try:
        license_id = int(license_id)
    except ValueError:
        return ApiResponse(err="Invalid license_id in URL", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getAllDocumentStatuses",
            params=[license_id]
        )

        document_types = result.get("documentTypes", [])
        statuses = result.get("verificationStatuses", [])
        remarks = result.get("remarks", [])

        # Check if all returned lists are empty
        if not document_types and not statuses and not remarks:
            return ApiResponse(
                err="No documents verified yet for this license.",
                status=HTTP_404_NOT_FOUND
            )

        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception("Fetch all document statuses failed")
        return ApiResponse(
            err=f"All document statuses fetch failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )

#15. add_inspection_feedback
@api_view(["POST"])
def add_inspection_feedback(request):
    """ Add feedback from an inspection for a license.
    Expected payload:
    {
        "license_id": 123,
        "inspector": "John Doe",
        "feedback_type": 0,
        "remarks": "Inspection passed"
    }
    """
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
        if not result.get("success"):
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        return ApiResponse(data=result, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Add inspection feedback failed")
        return ApiResponse(
            err=f"Inspection feedback submission failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
#16. Get All Inspection Feedback
@api_view(["GET"])
def get_all_inspection_feedback(request, license_id):
    """ Fetch all inspection feedback for a given license.
    """
    try:
        license_id = int(license_id)
    except ValueError:
        return ApiResponse(err="Invalid license_id in URL", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="getAllInspectionFeedback",
            params=[license_id]
        )

        # ✅ Check if result is empty or count is zero
        if not result:
            return ApiResponse(
                err="Physical verification not yet done for this license.",
                status=HTTP_404_NOT_FOUND
            )

        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception("Fetch inspection feedback failed")
        return ApiResponse(
            err=f"Inspection feedback fetch failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )


#17. Count Feedback by Type
@api_view(["GET"])
def count_feedback_by_type(request, license_id, feedback_type):
    """ Count the number of feedback entries for a specific type on a license.
    """
    try:
        license_id = int(license_id)
        feedback_type = int(feedback_type)
    except (ValueError, TypeError):
        return ApiResponse(
            err="Invalid license_id or feedback_type (must be integers).",
            status=HTTP_400_BAD_REQUEST
        )

    try:
        result = read_from_contract(
            contract_name="LicenseSystemV1",
            method_name="countFeedbackByType",
            params=[license_id, feedback_type]
        )

        # Assume 0 count means no feedback submitted for that type
        if result == 0:
            return ApiResponse(
                err=f"No feedback of type: {FEEDBACK_TYPES[feedback_type]} submitted for license ID {license_id}.",
                status=HTTP_404_NOT_FOUND
            )

        return ApiResponse(data={"count": result}, status=HTTP_200_OK)

    except Exception as e:
        logger.exception("Count feedback by type failed")
        return ApiResponse(
            err=f"Count feedback fetch failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )

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