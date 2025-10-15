from rest_framework.decorators import api_view
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR, HTTP_404_NOT_FOUND, HTTP_202_ACCEPTED
import logging
from django.conf import settings
from cryptography.hazmat.primitives import serialization

from .enums import LicenseStatusEnum, LICENSE_STATUS_REVERSE
from .serializers import SubmitLicenseApplicationSerializer, UpdateLicenseStatusSerializer, VerifyLicenseSerializer, UpdateLicenseDetailsSerializer

from utils.api_response import ApiResponse
from .services.blockchain import (
    write_to_contract,
    read_from_contract,
    get_transaction_status,
    get_available_methods,
    get_contract_address
)

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

# 0. Get Public Key
@api_view(["GET"])
def get_public_key(request):
    """
    Provides the public key for client-side encryption.
    """
    public_key = settings.GENERATED_PUBLIC_KEY 
    return ApiResponse(data=public_key, status=HTTP_200_OK)


# 1. Get Owner Address
@api_view(["GET"])
def check_owner_blockchain(request):
    # Endpoint to check the owner of the blockchain contract
    try:
        result = read_from_contract(
            method_name="owner",
            params=[],
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain read failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# 2. check total License count
@api_view(["GET"])
def check_total_license_count(request):
    """ Endpoint to get the total number of licenses created in the blockchain.
    This is useful for tracking the number of licenses issued.
    """
    try:
        result = read_from_contract(
            method_name="licenseIdCounter",
            params=[]
        )
        return ApiResponse(data=result, status=HTTP_200_OK)
    except ValueError as e:
        return ApiResponse(err=str(e), status=HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Blockchain write error")
        return ApiResponse(err=f"Blockchain write failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# 3. Submit License Application for all the levels
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
    struct_input = {
        "category": validated["license_category"],
        "level": validated["license_level"],
        "registeringAuthority": validated["registering_authority"],
        "registeringOfficeName": validated["registering_office_name"],
        "applicantName": validated["applicant_name"],
        "aadhaarNumber": validated["aadhaar_number"],
        "applicantPermanentAddress": validated["applicant_permanent_address"],
        "firmName": validated["firm_name"],
        "firmType": validated["firm_type"],
        "firmAddress": validated["firm_address"],
        "salePointAddress": validated["sale_point_address"],
        "saleStorageAddress": validated["sale_storage_address"],
        "productionCompany": validated["production_company"],
        "cropName": validated["crop_name"],
        "cropVariety": validated["crop_variety"],
    }

    try:
        result = write_to_contract(
            method_name="submitLicenseApplication",
            params=[struct_input],
            # address=address,
            # private_key=private_key
        )
       
        if not result.get("success", False):
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        
        # Return the transaction hash immediately with 202 status
        return ApiResponse(
            data={
                "transaction_hash": result.get("transaction_hash"),
                "status": "accepted",
                "message": "Transaction submitted successfully. Processing will continue in the background."
            }, 
            status=HTTP_202_ACCEPTED
        )

    except Exception as e:
        logger.exception("Create license failed")
        return ApiResponse(err=f"Create license failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)

# 4. get_license_basic_info
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
        result = read_from_contract(
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


# 5. Get License Action History
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
        result = read_from_contract(
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


# 6. Update License Status
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
    license_id = validated["license_id"]
    new_status = validated["status"]            
    remarks = validated["remarks"]
    officer_name = validated["officer_name"]
    role = validated["role"]                    
    renewal_period_days = validated.get("renewal_period_days", 0)

    try:
        # 1. Fetch current license info
        current_data = read_from_contract(
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

        if not result.get("success", False):
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        
        # Return the transaction hash immediately with 202 status
        return ApiResponse(
            data={
                "transaction_hash": result.get("transaction_hash"),
                "status": "accepted",
                "message": "Transaction submitted successfully. Processing will continue in the background."
            }, 
            status=HTTP_202_ACCEPTED
        )

    except Exception as e:
        logger.exception("Update license status failed")
        return ApiResponse(err=f"Update license status failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# 7. GET QR Code Data for License Verification
@api_view(["GET"])
def get_license_qr_data(request, license_id):
    """ Fetch QR code data for a license by ID.
    This data can be used to generate a QR code for easy verification.
    """
    try:
        license_id = int(license_id)
        if license_id <= 0:
            return ApiResponse(err="License ID must be positive integer", status=HTTP_400_BAD_REQUEST)
    except ValueError:
        return ApiResponse(err="License ID must be a valid integer", status=HTTP_400_BAD_REQUEST)

    try:
        result = read_from_contract(
            method_name="getLicenseQRData",
            params=[license_id]
        )

        return ApiResponse(data=result, status=HTTP_200_OK)

    except Exception as e:
        logger.exception(f"QR data fetch failed for license ID {license_id}")
        return ApiResponse(
            err=f"QR data fetch failed: {str(e)}",
            status=HTTP_500_INTERNAL_SERVER_ERROR
        )
    

# 8. Verify Integrity and Validity of License Document
@api_view(["POST"])
def verify_license_document(request):
    """ Verify a license document using its hash.
    Expected payload:
    {
        "license_number": "123",
        "expected_hash": "abc123897834377",
    }
    """
    serializer = VerifyLicenseSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    license_number = validated["license_number"]
    expected_hash = validated["expected_hash"]

    try:
        result = write_to_contract(
            method_name="verifyLicenseWithHash",
            params=[
                license_number,
                expected_hash
            ],
        )

        print("saghsadg", result)

        if not result.get("success", False):
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        
        # Return the transaction hash immediately with 202 status
        return ApiResponse(
            data={
                "transaction_hash": result.get("transaction_hash"),
                "status": "accepted",
                "message": "Transaction submitted successfully. Processing will continue in the background."
            }, 
            status=HTTP_202_ACCEPTED
        )

    except Exception as e:
        logger.exception("Verify document failed")
        return ApiResponse(err=f"Verify document failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# 9. Update License Details
@api_view(["POST"])
def update_license_details(request):
    """ Update details of an existing license.
    Expected payload:
    {
        "license_id": 123,
        "firm_name": "New Firm Name",
        "firm_type": "New Firm Type",
        "firm_address": "New Firm Address",
        "sale_point_address": "New Sale Point Address",
        "sale_storage_address": "New Sale Storage Address",
        "production_company": "New Production Company",
        "crop_name": "New Crop Name",
        "crop_variety": "New Crop Variety",
        "role": "JOINT_DIRECTOR"
    }
    """
    serializer = UpdateLicenseDetailsSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse(err=serializer.errors, status=HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    license_id = validated["license_id"]
    firm_name = validated.get("firm_name", "")
    firm_type = validated.get("firm_type", "")
    firm_address = validated.get("firm_address", "")
    sale_point_address = validated.get("sale_point_address", "")
    sale_storage_address = validated.get("sale_storage_address", "")
    production_company = validated.get("production_company", "")
    crop_name = validated.get("crop_name", "")
    crop_variety = validated.get("crop_variety", "")
    role = validated["role"]

    try:
        # Call contract method to update license details
        result = write_to_contract(
            method_name="updateLicenseDetails",
            params=[
                license_id,
                firm_name,
                firm_type,
                firm_address,
                sale_point_address,
                sale_storage_address,
                production_company,
                crop_name,
                crop_variety,
                role
            ],
        )

        if not result.get("success", False):
            return ApiResponse(data=result, status=HTTP_400_BAD_REQUEST)
        
        # Return the transaction hash immediately with 202 status
        return ApiResponse(
            data={
                "transaction_hash": result.get("transaction_hash"),
                "status": "accepted",
                "message": "Transaction submitted successfully. Processing will continue in the background."
            }, 
            status=HTTP_202_ACCEPTED
        )

    except Exception as e:
        logger.exception("Update license details failed")
        return ApiResponse(err=f"Update license details failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# Contract Information & Utilities
# 10. GET contract address
@api_view(["GET"])
def contract_address_view(request):
    """Get all available methods for a contract"""
    try:
        methods = get_contract_address()
        return ApiResponse(data=methods, status=200)
    except Exception as e:
        logger.exception("Contract methods error")
        return ApiResponse(err=f"Failed to get contract methods: {str(e)}", status=500)

# 11. GET all available methods
@api_view(["GET"])
def contract_methods_view(request):
    """Get all available methods for a contract"""
    try:
        methods = get_available_methods()
        return ApiResponse(data=methods, status=200)
    except Exception as e:
        logger.exception("Contract methods error")
        return ApiResponse(err=f"Failed to get contract methods: {str(e)}", status=500)

# 12. GET transaction status
@api_view(["GET"])
def transaction_status_view(request, tx_hash):
    """Get transaction status and details by hash"""
    try:
        status = get_transaction_status(tx_hash)
        return ApiResponse(data=status, status=200)
    except Exception as e:
        logger.exception("Transaction status error")
        return ApiResponse(err=f"Failed to get transaction status: {str(e)}", status=500)


